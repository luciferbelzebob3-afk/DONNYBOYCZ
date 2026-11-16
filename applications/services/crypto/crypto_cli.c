#include <furi_hal.h>
#include <furi.h>

#include <lib/toolbox/args.h>
#include <toolbox/pipe.h>
#include <cli/cli_main_commands.h>
#include <toolbox/cli/cli_command.h>
#include <toolbox/cli/cli_ansi.h>

void crypto_cli_print_usage(void) {
    printf("Pouziti:\r\n");
    printf("crypto <cmd> <args>\r\n");
    printf("Seznam prikazu:\r\n");
    printf(
        "\tencrypt <key_slot:int> <iv:hex>\t - Pomoci klice ze zabezpeceneho uloziste a IV zasifruje otevreny text pomoci AES256CBC a zakoduje ho do hexu\r\n");
    printf(
        "\tdecrypt <key_slot:int> <iv:hex>\t - Pomoci klice ze zabezpeceneho uloziste a IV rozsifruje data zakodovana v hexu pomoci AES256CBC na otevreny text\r\n");
    printf("\thas_key <key_slot:int>\t - Overit, zda zabezpeceny modul obsahuje klic ve slotu\r\n");
    printf(
        "\tstore_key <key_slot:int> <key_type:str> <key_size:int> <key_data:hex>\t - Ulozi klic do zabezpeceneho uloziste. !!! NEVRATNA OPERACE - NEJDRIVE SI PRECTI NAVOD !!!\r\n");
}

void crypto_cli_encrypt(PipeSide* pipe, FuriString* args) {
    int key_slot = 0;
    bool key_loaded = false;
    uint8_t iv[16];

    do {
        if(!args_read_int_and_trim(args, &key_slot) || !(key_slot > 0 && key_slot <= 100)) {
            printf("Chybejici nebo neplatny slot, ocekava se cele cislo 1-100");
            break;
        }

        if(!args_read_hex_bytes(args, iv, 16)) {
            printf("Chybejici nebo neplatne IV, ocekava se 16 bajtu v hex formatu");
            break;
        }

        if(!furi_hal_crypto_enclave_load_key(key_slot, iv)) {
            printf("Nepodarilo se nacist klic ze slotu %d", key_slot);
            break;
        }
        key_loaded = true;

        printf("Zadej prosty text a stiskni Ctrl+C pro dokonceni sifrovani:\r\n");

        FuriString* input;
        input = furi_string_alloc();
        char c;
        while(pipe_receive(pipe, (uint8_t*)&c, 1) == 1) {
            if(c == CliKeyETX) {
                printf("\r\n");
                break;
            } else if(c >= 0x20 && c < 0x7F) {
                putc(c, stdout);
                fflush(stdout);
                furi_string_push_back(input, c);
            } else if(c == CliKeyCR) {
                printf("\r\n");
                furi_string_cat(input, "\r\n");
            }
        }

        size_t size = furi_string_size(input);
        if(size > 0) {
            // C-string null termination and block alignments
            size++;
            size_t remain = size % 16;
            if(remain) {
                size = size - remain + 16;
            }
            furi_string_reserve(input, size);
            uint8_t* output = malloc(size);
            if(!furi_hal_crypto_encrypt(
                   (const uint8_t*)furi_string_get_cstr(input), output, size)) {
                printf("Nepodarilo se zasifrovat vstup");
            } else {
                printf("Zasifrovana data v hex formatu:\r\n");
                for(size_t i = 0; i < size; i++) {
                    if(i % 80 == 0) printf("\r\n");
                    printf("%02x", output[i]);
                }
                printf("\r\n");
            }
            free(output);
        } else {
            printf("Zadny vstup");
        }

        furi_string_free(input);
    } while(0);

    if(key_loaded) {
        furi_hal_crypto_enclave_unload_key(key_slot);
    }
}

void crypto_cli_decrypt(PipeSide* pipe, FuriString* args) {
    int key_slot = 0;
    bool key_loaded = false;
    uint8_t iv[16];

    do {
        if(!args_read_int_and_trim(args, &key_slot) || !(key_slot > 0 && key_slot <= 100)) {
            printf("Chybejici nebo neplatny slot, ocekava se cele cislo 1-100");
            break;
        }

        if(!args_read_hex_bytes(args, iv, 16)) {
            printf("Chybejici nebo neplatne IV, ocekava se 16 bajtu v hex formatu");
            break;
        }

        if(!furi_hal_crypto_enclave_load_key(key_slot, iv)) {
            printf("Nepodarilo se nacist klic ze slotu %d", key_slot);
            break;
        }
        key_loaded = true;

        printf("Zadej data v hex formatu a stiskni Ctrl+C pro dokonceni desifrovani:\r\n");

        FuriString* hex_input;
        hex_input = furi_string_alloc();
        char c;
        while(pipe_receive(pipe, (uint8_t*)&c, 1) == 1) {
            if(c == CliKeyETX) {
                printf("\r\n");
                break;
            } else if(c >= 0x20 && c < 0x7F) {
                putc(c, stdout);
                fflush(stdout);
                furi_string_push_back(hex_input, c);
            } else if(c == CliKeyCR) {
                printf("\r\n");
            }
        }

        furi_string_trim(hex_input);
        size_t hex_size = furi_string_size(hex_input);
        if(hex_size > 0 && hex_size % 2 == 0) {
            size_t size = hex_size / 2;
            uint8_t* input = malloc(size);
            uint8_t* output = malloc(size);

            if(args_read_hex_bytes(hex_input, input, size)) {
                if(furi_hal_crypto_decrypt(input, output, size)) {
                    printf("Desifrovana data:\r\n");
                    printf("%s\r\n", output); //-V576
                } else {
                    printf("Desifrovani selhalo\r\n");
                }
            } else {
                printf("Nepodarilo se zpracovat vstup");
            }

            free(input);
            free(output);
        } else {
            printf("Neplatny nebo prazdny vstup");
        }

        furi_string_free(hex_input);
    } while(0);

    if(key_loaded) {
        furi_hal_crypto_enclave_unload_key(key_slot);
    }
}

void crypto_cli_has_key(PipeSide* pipe, FuriString* args) {
    UNUSED(pipe);
    int key_slot = 0;
    uint8_t iv[16] = {0};

    do {
        if(!args_read_int_and_trim(args, &key_slot) || !(key_slot > 0 && key_slot <= 100)) {
            printf("Chybejici nebo neplatny slot, ocekava se cele cislo 1-100");
            break;
        }

        if(!furi_hal_crypto_enclave_load_key(key_slot, iv)) {
            printf("Nepodarilo se nacist klic ze slotu %d", key_slot);
            break;
        }

        printf("Klic ze slotu %d byl uspesne nacten", key_slot);

        furi_hal_crypto_enclave_unload_key(key_slot);
    } while(0);
}

void crypto_cli_store_key(PipeSide* pipe, FuriString* args) {
    UNUSED(pipe);
    int key_slot = 0;
    int key_size = 0;
    FuriString* key_type;
    key_type = furi_string_alloc();

    uint8_t data[32 + 12] = {};
    FuriHalCryptoKey key;
    key.data = data;
    size_t data_size = 0;

    do {
        if(!args_read_int_and_trim(args, &key_slot)) {
            printf("Chybejici nebo neplatny typ klice, ocekava se master, simple nebo encrypted");
            break;
        }
        if(!args_read_string_and_trim(args, key_type)) {
            printf("Chybejici nebo neplatny typ klice, ocekava se master, simple nebo encrypted");
            break;
        }

        if(furi_string_cmp_str(key_type, "master") == 0) {
            if(key_slot != 0) {
                printf("Slot hlavniho klice musi byt 0");
                break;
            }
            key.type = FuriHalCryptoKeyTypeMaster;
        } else if(furi_string_cmp_str(key_type, "simple") == 0) {
            if(key_slot < 1 || key_slot > 99) {
                printf("Slot jednoducheho klice je mimo povoleny rozsah");
                break;
            }
            key.type = FuriHalCryptoKeyTypeSimple;
        } else if(furi_string_cmp_str(key_type, "encrypted") == 0) {
            key.type = FuriHalCryptoKeyTypeEncrypted;
            data_size += 12;
        } else {
            printf("Chybejici nebo neplatny typ klice, ocekava se master, simple nebo encrypted");
            break;
        }

        if(!args_read_int_and_trim(args, &key_size)) {
            printf("Chybejici nebo neplatna delka klice, ocekava se 128 nebo 256");
            break;
        }

        if(key_size == 128) {
            key.size = FuriHalCryptoKeySize128;
            data_size += 16;
        } else if(key_size == 256) {
            key.size = FuriHalCryptoKeySize256;
            data_size += 32;
        } else {
            printf("Chybejici nebo neplatna delka klice, ocekava se 128 nebo 256");
        }

        if(!args_read_hex_bytes(args, data, data_size)) {
            printf("Chybejici nebo neplatna data klice, ocekava se klic v hex formatu s IV nebo bez nej.");
            break;
        }

        if(key_slot > 0) {
            uint8_t iv[16] = {0};
            if(key_slot > 1) {
                if(!furi_hal_crypto_enclave_load_key(key_slot - 1, iv)) {
                    printf(
                        "Slot %d pred slotem %d je prazdny, coz neni povoleno",
                        key_slot - 1,
                        key_slot);
                    break;
                }
                furi_hal_crypto_enclave_unload_key(key_slot - 1);
            }

            if(furi_hal_crypto_enclave_load_key(key_slot, iv)) {
                furi_hal_crypto_enclave_unload_key(key_slot);
                printf("Slot klice %d je jiz obsazen", key_slot);
                break;
            }
        }

        uint8_t slot;
        if(furi_hal_crypto_enclave_store_key(&key, &slot)) {
            printf("Ulozeno do pozice: %d", slot);
        } else {
            printf("Chyba");
        }
    } while(0);

    furi_string_free(key_type);
}

static void crypto_cli(PipeSide* pipe, FuriString* args, void* context) {
    UNUSED(context);
    FuriString* cmd;
    cmd = furi_string_alloc();

    do {
        if(!args_read_string_and_trim(args, cmd)) {
            crypto_cli_print_usage();
            break;
        }

        if(furi_string_cmp_str(cmd, "encrypt") == 0) {
            crypto_cli_encrypt(pipe, args);
            break;
        }

        if(furi_string_cmp_str(cmd, "decrypt") == 0) {
            crypto_cli_decrypt(pipe, args);
            break;
        }

        if(furi_string_cmp_str(cmd, "has_key") == 0) {
            crypto_cli_has_key(pipe, args);
            break;
        }

        if(furi_string_cmp_str(cmd, "store_key") == 0) {
            crypto_cli_store_key(pipe, args);
            break;
        }

        crypto_cli_print_usage();
    } while(false);

    furi_string_free(cmd);
}

CLI_COMMAND_INTERFACE(crypto, crypto_cli, CliCommandFlagDefault, 4 * 1024, CLI_APPID);
