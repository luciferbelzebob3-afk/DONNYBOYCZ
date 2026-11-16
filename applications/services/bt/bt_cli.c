#include <furi.h>
#include <furi_hal.h>
#include <lib/toolbox/args.h>
#include <toolbox/pipe.h>
#include <cli/cli_main_commands.h>
#include <toolbox/cli/cli_command.h>

#include <ble/ble.h>
#include "bt_settings.h"
#include "bt_service/bt.h"
#include <profiles/serial_profile.h>

static void bt_cli_command_hci_info(PipeSide* pipe, FuriString* args, void* context) {
    UNUSED(pipe);
    UNUSED(args);
    UNUSED(context);
    FuriString* buffer;
    buffer = furi_string_alloc();
    furi_hal_bt_dump_state(buffer);
    printf("%s", furi_string_get_cstr(buffer));
    furi_string_free(buffer);
}

static void bt_cli_command_carrier_tx(PipeSide* pipe, FuriString* args, void* context) {
    UNUSED(context);
    int channel = 0;
    int power = 0;

    do {
        if(!args_read_int_and_trim(args, &channel) && (channel < 0 || channel > 39)) {
            printf("Chybi nebo je neplatny kanal, ocekava se cele cislo 0-39");
            break;
        }
        if(!args_read_int_and_trim(args, &power) && (power < 0 || power > 6)) {
            printf("Chybi nebo je neplatny vykon, ocekava se cele cislo 0-6");
            break;
        }

        Bt* bt = furi_record_open(RECORD_BT);
        bt_disconnect(bt);
        furi_hal_bt_reinit();
        printf("Vysilam nosnou na kanalu %d s vykonem %d dB\r\n", channel, power);
        printf("Stiskni CTRL+C pro zastaveni\r\n");
        furi_hal_bt_start_tone_tx(channel, 0x19 + power);

        while(!cli_is_pipe_broken_or_is_etx_next_char(pipe)) {
            furi_delay_ms(250);
        }
        furi_hal_bt_stop_tone_tx();

        bt_profile_restore_default(bt);
        furi_record_close(RECORD_BT);
    } while(false);
}

static void bt_cli_command_carrier_rx(PipeSide* pipe, FuriString* args, void* context) {
    UNUSED(context);
    int channel = 0;

    do {
        if(!args_read_int_and_trim(args, &channel) && (channel < 0 || channel > 39)) {
            printf("Chybi nebo je neplatny kanal, ocekava se cele cislo 0-39");
            break;
        }

        Bt* bt = furi_record_open(RECORD_BT);
        bt_disconnect(bt);
        furi_hal_bt_reinit();
        printf("Prijem nosne na kanalu %d\r\n", channel);
        printf("Stiskni CTRL+C pro zastaveni\r\n");

        furi_hal_bt_start_packet_rx(channel, 1);

        while(!cli_is_pipe_broken_or_is_etx_next_char(pipe)) {
            furi_delay_ms(250);
            printf("RSSI: %6.1f dB\r", (double)furi_hal_bt_get_rssi());
            fflush(stdout);
        }

        furi_hal_bt_stop_packet_test();

        bt_profile_restore_default(bt);
        furi_record_close(RECORD_BT);
    } while(false);
}

static void bt_cli_command_packet_tx(PipeSide* pipe, FuriString* args, void* context) {
    UNUSED(context);
    int channel = 0;
    int pattern = 0;
    int datarate = 1;

    do {
        if(!args_read_int_and_trim(args, &channel) && (channel < 0 || channel > 39)) {
            printf("Chybi nebo je neplatny kanal, ocekava se cele cislo 0-39");
            break;
        }
        if(!args_read_int_and_trim(args, &pattern) && (pattern < 0 || pattern > 5)) {
            printf("Chybi nebo je neplatny vzor, ocekava se cele cislo 0-5\r\n");
            printf("0 - Pseudonahodna bitova posloupnost 9\r\n");
            printf("1 - Stridajici se bity '11110000'\r\n");
            printf("2 - Stridajici se bity '10101010'\r\n");
            printf("3 - Pseudonahodna bitova posloupnost 15\r\n");
            printf("4 - Pouze bity '1'\r\n");
            printf("5 - Pouze bity '0'\r\n");
            break;
        }
        if(!args_read_int_and_trim(args, &datarate) && (datarate < 1 || datarate > 2)) {
            printf("Chybi nebo je neplatna rychlost prenosu, ocekava se cele cislo 1-2");
            break;
        }

        Bt* bt = furi_record_open(RECORD_BT);
        bt_disconnect(bt);
        furi_hal_bt_reinit();
        printf(
            "Vysilam paket se vzorem %d na kanalu %d rychlosti %d M\r\n",
            pattern,
            channel,
            datarate);
        printf("Stiskni CTRL+C pro zastaveni\r\n");
        furi_hal_bt_start_packet_tx(channel, pattern, datarate);

        while(!cli_is_pipe_broken_or_is_etx_next_char(pipe)) {
            furi_delay_ms(250);
        }
        furi_hal_bt_stop_packet_test();
        printf("Odeslano paketu: %lu", furi_hal_bt_get_transmitted_packets());

        bt_profile_restore_default(bt);
        furi_record_close(RECORD_BT);
    } while(false);
}

static void bt_cli_command_packet_rx(PipeSide* pipe, FuriString* args, void* context) {
    UNUSED(context);
    int channel = 0;
    int datarate = 1;

    do {
        if(!args_read_int_and_trim(args, &channel) && (channel < 0 || channel > 39)) {
            printf("Chybi nebo je neplatny kanal, ocekava se cele cislo 0-39");
            break;
        }
        if(!args_read_int_and_trim(args, &datarate) && (datarate < 1 || datarate > 2)) {
            printf("Chybi nebo je neplatna rychlost prenosu, ocekava se cele cislo 1-2");
            break;
        }

        Bt* bt = furi_record_open(RECORD_BT);
        bt_disconnect(bt);
        furi_hal_bt_reinit();
        printf("Prijem paketu na kanalu %d, rychlost %d M\r\n", channel, datarate);
        printf("Stiskni CTRL+C pro zastaveni\r\n");
        furi_hal_bt_start_packet_rx(channel, datarate);

        while(!cli_is_pipe_broken_or_is_etx_next_char(pipe)) {
            furi_delay_ms(250);
            printf("RSSI: %03.1f dB\r", (double)furi_hal_bt_get_rssi());
            fflush(stdout);
        }
        uint16_t packets_received = furi_hal_bt_stop_packet_test();
        printf("Prijato paketu: %hu", packets_received);

        bt_profile_restore_default(bt);
        furi_record_close(RECORD_BT);
    } while(false);
}

static void bt_cli_print_usage(void) {
    printf("Pouziti:\r\n");
    printf("bt <cmd> <args>\r\n");
    printf("Seznam prikazu:\r\n");
    printf("\thci_info\t - informace HCI\r\n");
    if(furi_hal_rtc_is_flag_set(FuriHalRtcFlagDebug) && furi_hal_bt_is_testing_supported()) {
        printf("\ttx_carrier <kanal:0-39> <vykon:0-6>\t - spustit test vysilani nosne\r\n");
        printf("\trx_carrier <kanal:0-39>\t - spustit test prijmu nosne\r\n");
        printf(
            "\ttx_packet <kanal:0-39> <vzor:0-5> <rychlost:1-2>\t - spustit test vysilani paketu\r\n");
        printf("\trx_packet <kanal:0-39> <rychlost:1-2>\t - spustit test prijmu paketu\r\n");
    }
}

static void bt_cli(PipeSide* pipe, FuriString* args, void* context) {
    UNUSED(context);
    furi_record_open(RECORD_BT);

    FuriString* cmd;
    cmd = furi_string_alloc();
    BtSettings bt_settings;
    bt_settings_load(&bt_settings);

    do {
        if(!args_read_string_and_trim(args, cmd)) {
            bt_cli_print_usage();
            break;
        }
        if(furi_string_cmp_str(cmd, "hci_info") == 0) {
            bt_cli_command_hci_info(pipe, args, NULL);
            break;
        }
        if(furi_hal_rtc_is_flag_set(FuriHalRtcFlagDebug) && furi_hal_bt_is_testing_supported()) {
            if(furi_string_cmp_str(cmd, "tx_carrier") == 0) {
                bt_cli_command_carrier_tx(pipe, args, NULL);
                break;
            }
            if(furi_string_cmp_str(cmd, "rx_carrier") == 0) {
                bt_cli_command_carrier_rx(pipe, args, NULL);
                break;
            }
            if(furi_string_cmp_str(cmd, "tx_packet") == 0) {
                bt_cli_command_packet_tx(pipe, args, NULL);
                break;
            }
            if(furi_string_cmp_str(cmd, "rx_packet") == 0) {
                bt_cli_command_packet_rx(pipe, args, NULL);
                break;
            }
        }

        bt_cli_print_usage();
    } while(false);

    if(bt_settings.enabled) {
        furi_hal_bt_start_advertising();
    }

    furi_string_free(cmd);
    furi_record_close(RECORD_BT);
}

CLI_COMMAND_INTERFACE(bt, bt_cli, CliCommandFlagDefault, 4 * 1024, CLI_APPID);
