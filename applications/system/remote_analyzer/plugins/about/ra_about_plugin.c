/**
 * @file ra_about_plugin.c
 * @brief Entry point of the How to use .fal: the manual, and the widget it scrolls in.
 */
#include "../../helpers/ra_about_plugin.h"

#include <flipper_application/flipper_application.h>
#include <gui/modules/widget.h>
#include <furi.h>

/* The scroll element only reads a control marker at the start of a line, so each heading
 * carries one \e# and no closing marker, and the next \n ends the bold. It wraps per
 * character rather than per word, so the breaks are placed here: every line is inside the
 * 124px the element leaves beside its scrollbar. */
/* clang-format off */
static const char* ra_about_text =
    "\e#Analyzator ovladacu\n"
    "Cte jeden ovladac internim\n"
    "radiem a zobrazi rozpoznana\n"
    "pole. Zobrazuje jeden signal\n"
    "bez historie.\n"
    "\n"
    "\e#Dalsi protokoly\n"
    "Krome protokolu Sub-GHz\n"
    "aplikace sama rozpoznava:\n"
    "Crypt, Crypt Lite,\n"
    "Hormann BiSecur, KCE6xxx,\n"
    "Life Fido, Nero Intro II,\n"
    "PC4.\n"
    "\n"
    "\e#Cteni\n"
    "V Nastaveni vyber frekvenci\n"
    "a modulaci. Priloz ovladac\n"
    "a stiskni jeho tlacitko.\n"
    "Ikona vlevo nahore oznacuje\n"
    "pevny nebo plovouci kod.\n"
    "Pruh ukazuje silu signalu.\n"
    "Nahoru a Dolu posouvaji\n"
    "text, ktery se nevejde.\n"
    "\n"
    "\e#LED\n"
    "Fialova: prijem.\n"
    "Zluta: signal bez dekodovani.\n"
    "Zelena: kod rozpoznan.\n"
    "\n"
    "\e#Upozorneni\n"
    "Zavibruje jednou pri kodu,\n"
    "ktery se lisi od minuleho.\n"
    "Drzene tlacitko opakuje\n"
    "stejny kod; blika jen LED.\n"
    "\n"
    "\e#Hledani modulace\n"
    "Pokud ovladac vysila, ale\n"
    "kod neni rozpoznan, zkousi\n"
    "se kazdou sekundu dalsi\n"
    "modulace. Znak ~ znamena,\n"
    "ze hledani stale probiha.\n"
    "Tlacitko ovladace drz.\n"
    "Prvni rozpoznany kod ustali\n"
    "modulaci a znak ~ zmizi.\n"
    "Po dvou sekundach bez kodu\n"
    "hledani pokracuje od teto\n"
    "modulace.\n"
    "Neznamy ovladac znamena,\n"
    "ze cele kolo nic nenaslo.\n"
    "Hledani se pak opakuje.\n"
    "\n"
    "\e#Prepinani pasem\n"
    "VYP. nebo prah sily signalu.\n"
    "Bez signalu strida pasma\n"
    "315, 390, 430.5, 433.92,\n"
    "434.42 a 868.35 MHz.\n"
    "Zastavi na prvnim signalu.\n"
    "Rozpoznany kod podrzi pasmo\n"
    "dve sekundy; pak pokracuje.\n"
    "Frekvence v Nastaveni se\n"
    "pritom nepouziva. Rucni\n"
    "vyber v analyzatoru frekv.\n"
    "prepinani pasem vypne.\n"
    "Prah pouziva take hledani\n"
    "modulace a LED, i kdyz je\n"
    "prepinani pasem vypnute.\n"
    "\n"
    "\e#Dekodovat RAW\n"
    "Ulozeny .sub zaznam prochazi\n"
    "stejnymi dekodery. Pruh\n"
    "ukazuje postup. Nakonec\n"
    "uvidis seznam ruznych kodu.\n"
    "Stiskem OK zobrazis detail.\n"
    "Vzorky obsahuje jen RAW;\n"
    "soubor s klicem nestaci.\n"
    "Prazdny vysledek nebo\n"
    "nevhodny soubor oznami\n"
    "chyba a cervena LED.\n"
    "\n"
    "\e#Analyzator frekv.\n"
    "Najde frekvenci ovladace.\n"
    "Drz tlacitko ovladace a pak\n"
    "podrz OK: frekvence se\n"
    "prenese do Cteni. Vlevo\n"
    "a Vpravo meni prah signalu.\n"
    "\n"
    "\e#Druhy radek\n"
    "Pod nazvem protokolu a poctem\n"
    "bitu je uvedeno, zda ho umi\n"
    "i aplikace Sub-GHz, nebo\n"
    "jen tento analyzator.\n";
/* clang-format on */

/** One manual at a time, and each scene entry maps a fresh copy of the plugin. */
static Widget* ra_about_widget = NULL;

static void ra_about_plugin_on_enter(RaAboutEnv* env) {
    furi_assert(env);
    furi_assert(!ra_about_widget);

    ra_about_widget = widget_alloc();
    widget_add_text_scroll_element(ra_about_widget, 0, 0, 128, 64, ra_about_text);
    view_dispatcher_add_view(env->view_dispatcher, env->view_id, widget_get_view(ra_about_widget));
    view_dispatcher_switch_to_view(env->view_dispatcher, env->view_id);
}

static void ra_about_plugin_on_exit(RaAboutEnv* env) {
    furi_assert(env);
    furi_assert(ra_about_widget);

    /* Park on an app-owned view before dropping ours: removing the current view leaves the
     * dispatcher with none, which stops the event loop for good. */
    view_dispatcher_switch_to_view(env->view_dispatcher, env->park_view_id);
    view_dispatcher_remove_view(env->view_dispatcher, env->view_id);

    widget_free(ra_about_widget);
    ra_about_widget = NULL;
}

static const RaAboutPlugin ra_about_plugin = {
    .on_enter = ra_about_plugin_on_enter,
    .on_exit = ra_about_plugin_on_exit,
};

static const FlipperAppPluginDescriptor ra_about_plugin_descriptor = {
    .appid = RA_ABOUT_PLUGIN_APP_ID,
    .ep_api_version = RA_ABOUT_PLUGIN_API_VERSION,
    .entry_point = &ra_about_plugin,
};

const FlipperAppPluginDescriptor* remote_analyzer_about_ep(void) {
    return &ra_about_plugin_descriptor;
}
