"""Provision a pinned CPU-only llama.cpp model on the runner, never a cloud API."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

LOCK_PATH = Path(__file__).resolve().parents[3] / '.donny/local-model.lock.json'


class RuntimeUnavailable(RuntimeError):
    pass


def lock_config():
    return json.loads(LOCK_PATH.read_text())


def assets_dir():
    return Path(os.environ.get('LOCAL_MODEL_ASSETS', str(Path(tempfile.gettempdir()) / 'donny-local-model')))


def checksum(path):
    sha = hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda: file.read(4 * 1024 * 1024), b''):
            sha.update(block)
    return sha.hexdigest()


def verify_model(path, expected):
    return Path(path).is_file() and checksum(path) == expected


def download_model(config, root):
    folder = root / 'models'
    folder.mkdir(parents=True, exist_ok=True)
    model = folder / config['model_file']
    if verify_model(model, config['model_sha256']):
        return model
    model.unlink(missing_ok=True)
    url = (f'https://huggingface.co/{config["model_repository"]}/resolve/'
           f'{config["model_revision"]}/{config["model_file"]}')
    partial = model.with_suffix('.download')
    print('Stahuji pripnuty model Qwen na server GitHubu.', flush=True)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=120) as response, partial.open('wb') as file:
                shutil.copyfileobj(response, file, 4 * 1024 * 1024)
            break
        except (OSError, TimeoutError):
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise RuntimeUnavailable('Model se nepodarilo stahnout. Neni pouzita zadna placena zaloha.') from None
            time.sleep(2 ** attempt)
    if not verify_model(partial, config['model_sha256']):
        partial.unlink(missing_ok=True)
        raise RuntimeError('Model nema ocekavany SHA-256. Spusteni bylo zablokovano.')
    partial.replace(model)
    print('Model GGUF: SHA-256 souhlasi.', flush=True)
    return model


def build_runtime(config, root):
    source = root / 'llama.cpp'
    build = source / 'build'
    binary = build / 'bin/llama-server'
    stamp = root / 'runtime-commit.txt'
    if binary.is_file() and stamp.is_file() and stamp.read_text().strip() == config['runtime_commit']:
        return binary
    source.mkdir(parents=True, exist_ok=True)
    log = root / 'runtime-build.log'
    commands = [
        ['git', 'init', str(source)],
        ['git', '-C', str(source), 'fetch', '--depth=1', config['runtime_repository'], config['runtime_commit']],
        ['git', '-C', str(source), 'checkout', '--detach', 'FETCH_HEAD'],
        ['cmake', '-S', str(source), '-B', str(build), '-DCMAKE_BUILD_TYPE=Release',
         '-DGGML_NATIVE=OFF', '-DGGML_CUDA=OFF', '-DGGML_VULKAN=OFF',
         '-DLLAMA_BUILD_TESTS=OFF', '-DLLAMA_BUILD_EXAMPLES=OFF', '-DLLAMA_BUILD_SERVER=ON',
         '-DLLAMA_CURL=OFF', '-DLLAMA_OPENSSL=OFF'],
        ['cmake', '--build', str(build), '--config', 'Release', '--target', 'llama-server', '-j', '4'],
    ]
    print('Sestavuji pripnuty llama.cpp pro CPU.', flush=True)
    with log.open('w') as file:
        for command in commands:
            result = subprocess.run(command, stdout=file, stderr=subprocess.STDOUT, timeout=900)
            if result.returncode:
                raise RuntimeError('Sestaveni lokalniho runtime selhalo; diagnostika: runtime-build.log')
    if not binary.is_file():
        raise RuntimeError('Chybi sestaveny llama-server.')
    stamp.write_text(config['runtime_commit'] + '\n')
    return binary


def healthy(port, expected_model):
    try:
        # Ignore proxy variables for runner-local traffic. No redirect to a cloud provider.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'http://127.0.0.1:{int(port)}/v1/models', timeout=3) as response:
            data = json.load(response)
        return any(item.get('id') == expected_model for item in data.get('data', []))
    except (OSError, ValueError, TypeError):
        return False


def ensure_server():
    config = lock_config()
    root = assets_dir()
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / 'server.json'
    # Each Actions job has its own assets folder and network namespace.
    with (root / 'provision.lock').open('w') as provision:
        fcntl.flock(provision, fcntl.LOCK_EX)
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text())
                os.kill(state['pid'], 0)
                if (state.get('model_sha256') == config['model_sha256'] and
                        state.get('runtime_commit') == config['runtime_commit'] and
                        healthy(state['port'], config['model_id'])):
                    return f'http://127.0.0.1:{int(state["port"])}/v1/chat/completions', config
            except (OSError, ValueError, KeyError):
                pass
        model = download_model(config, root)
        binary = build_runtime(config, root)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        log = (root / 'server.log').open('ab')
        command = [str(binary), '--model', str(model), '--alias', config['model_id'],
                   '--host', '127.0.0.1', '--port', str(port), '--threads', '4',
                   '--threads-batch', '4', '--ctx-size', str(config['context_tokens']),
                   '--parallel', '1', '--n-gpu-layers', '0', '--jinja',
                   '--reasoning', 'off', '--reasoning-budget', '0', '--no-webui']
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        log.close()
        state = dict(pid=process.pid, port=port, model_sha256=config['model_sha256'],
                     runtime_commit=config['runtime_commit'])
        state_path.write_text(json.dumps(state))
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('llama-server se ukoncil pri startu; viz server.log')
            if healthy(port, config['model_id']):
                print('Qwen je pripraven na CPU; inference pouze pres 127.0.0.1.', flush=True)
                return f'http://127.0.0.1:{port}/v1/chat/completions', config
            time.sleep(1)
        process.terminate()
        raise RuntimeUnavailable('Lokalni model se nestihl spustit.')
