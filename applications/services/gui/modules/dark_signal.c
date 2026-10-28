#include "dark_signal.h"

#include <assets_icons.h>
#include <gui/elements.h>
#include <gui/icon_animation_i.h>
#include <string.h>
#include <stdlib.h>

typedef enum {
    SignalApps,
    SignalRadio,
    SignalNfc,
    SignalRfid,
    SignalInfrared,
    SignalGpio,
    SignalKey,
    SignalUsb,
    SignalSettings,
} SignalIcon;

static SignalIcon dark_signal_icon_kind(const Icon* icon) {
    if(icon == &A_Sub1ghz_14) return SignalRadio;
    if(icon == &A_NFC_14) return SignalNfc;
    if(icon == &A_125khz_14) return SignalRfid;
    if(icon == &A_Infrared_14) return SignalInfrared;
    if(icon == &A_GPIO_14) return SignalGpio;
    if(icon == &A_iButton_14 || icon == &A_U2F_14) return SignalKey;
    if(icon == &A_BadUsb_14) return SignalUsb;
    if(icon == &A_Settings_14) return SignalSettings;
    return SignalApps;
}

/* The same 14-pixel geometry supplies both side icons and the 2x selected icon. */
static void signal_pixel(Canvas* c, int32_t x, int32_t y, int s, int px, int py) {
    canvas_draw_box(c, x + px * s, y + py * s, s, s);
}

static void signal_line(Canvas* c, int32_t x, int32_t y, int s, int x0, int y0, int x1, int y1) {
    int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    int error = dx + dy;
    while(true) {
        signal_pixel(c, x, y, s, x0, y0);
        if(x0 == x1 && y0 == y1) break;
        const int e2 = 2 * error;
        if(e2 >= dy) {
            error += dy;
            x0 += sx;
        }
        if(e2 <= dx) {
            error += dx;
            y0 += sy;
        }
    }
}

static void signal_frame(Canvas* c, int32_t x, int32_t y, int s, int w, int h) {
    signal_line(c, x, y, s, 0, 0, w - 1, 0);
    signal_line(c, x, y, s, 0, h - 1, w - 1, h - 1);
    signal_line(c, x, y, s, 0, 0, 0, h - 1);
    signal_line(c, x, y, s, w - 1, 0, w - 1, h - 1);
}

static void signal_icon(Canvas* c, int32_t x, int32_t y, int s, SignalIcon kind, bool pulse) {
    switch(kind) {
    case SignalRadio:
        signal_line(c, x, y, s, 7, 4, 3, 13);
        signal_line(c, x, y, s, 7, 4, 11, 13);
        signal_line(c, x, y, s, 5, 10, 9, 10);
        signal_pixel(c, x, y, s, 7, 3);
        signal_line(c, x, y, s, 4, 2, 3, 3);
        signal_line(c, x, y, s, 3, 3, 4, 5);
        signal_line(c, x, y, s, 10, 2, 11, 3);
        signal_line(c, x, y, s, 11, 3, 10, 5);
        if(!pulse) {
            signal_line(c, x, y, s, 2, 0, 0, 3);
            signal_line(c, x, y, s, 0, 3, 2, 7);
            signal_line(c, x, y, s, 12, 0, 13, 3);
            signal_line(c, x, y, s, 13, 3, 12, 7);
        }
        break;
    case SignalNfc:
    case SignalGpio:
        signal_frame(c, x + 3 * s, y + 3 * s, s, 8, 8);
        for(int i = 4; i <= 10; i += 3) {
            signal_line(c, x, y, s, i, 0, i, 2);
            signal_line(c, x, y, s, i, 11, i, 13);
            signal_line(c, x, y, s, 0, i, 2, i);
            signal_line(c, x, y, s, 11, i, 13, i);
        }
        if(kind == SignalNfc && s == 2) {
            canvas_draw_box(c, x + 3 * s, y + 3 * s, 8 * s, 8 * s);
            canvas_set_color(c, ColorBlack);
            canvas_set_font(c, FontBatteryPercent);
            canvas_draw_str_aligned(c, x + 14, y + 14, AlignCenter, AlignCenter, "NFC");
            canvas_set_color(c, ColorWhite);
        } else {
            signal_line(c, x, y, s, 5, 5, 8, 8);
            signal_line(c, x, y, s, 8, 5, 5, 8);
        }
        break;
    case SignalInfrared:
        signal_frame(c, x + 4 * s, y + 6 * s, s, 6, 8);
        signal_pixel(c, x, y, s, 6, 8);
        signal_pixel(c, x, y, s, 6, 11);
        signal_line(c, x, y, s, 4, 3, 7, 2);
        signal_line(c, x, y, s, 7, 2, 10, 3);
        if(!pulse) {
            signal_line(c, x, y, s, 2, 1, 7, 0);
            signal_line(c, x, y, s, 7, 0, 12, 1);
        }
        break;
    case SignalRfid:
        signal_frame(c, x + s, y + 3 * s, s, 12, 9);
        signal_frame(c, x + 3 * s, y + 5 * s, s, 4, 4);
        signal_line(c, x, y, s, 9, 6, 10, 7);
        signal_line(c, x, y, s, 10, 7, 9, 9);
        break;
    case SignalKey:
        signal_frame(c, x + s, y + s, s, 7, 7);
        signal_line(c, x, y, s, 7, 7, 12, 12);
        signal_line(c, x, y, s, 10, 10, 12, 8);
        signal_line(c, x, y, s, 12, 12, 13, 11);
        break;
    case SignalUsb:
        signal_frame(c, x + 4 * s, y, s, 6, 4);
        signal_frame(c, x + 2 * s, y + 4 * s, s, 10, 10);
        signal_pixel(c, x, y, s, 5, 1);
        signal_pixel(c, x, y, s, 8, 1);
        signal_line(c, x, y, s, 5, 8, 9, 8);
        break;
    case SignalSettings:
        signal_frame(c, x + 3 * s, y + 3 * s, s, 8, 8);
        signal_frame(c, x + 6 * s, y + 6 * s, s, 2, 2);
        for(int i = 5; i < 9; ++i) {
            signal_line(c, x, y, s, i, 1, i, 2);
            signal_line(c, x, y, s, i, 11, i, 12);
            signal_line(c, x, y, s, 1, i, 2, i);
            signal_line(c, x, y, s, 11, i, 12, i);
        }
        break;
    default:
        for(int row = 0; row < 2; row++) {
            for(int col = 0; col < 2; col++) {
                signal_frame(c, x + (1 + col * 7) * s, y + (1 + row * 7) * s, s, 5, 5);
            }
        }
        break;
    }
}

void dark_signal_menu_draw(Canvas* canvas, MenuModel* model) {
    canvas_set_color(canvas, ColorBlack);
    canvas_draw_box(canvas, 0, 0, canvas_width(canvas), canvas_height(canvas));
    canvas_set_color(canvas, ColorWhite);
    const int32_t center = canvas_width(canvas) / 2;
    const int32_t top = (canvas_height(canvas) - 64) / 2;
    const MenuItem* item = &model->items[model->position];
    SignalIcon kind = dark_signal_icon_kind(item->icon->icon);
    canvas_draw_rframe(canvas, center - 22, top + 7, 44, 39, 4);
    signal_icon(canvas, center - 14, top + 12, 2, kind, model->scroll_counter % 6 == 5);
    if(kind == SignalApps) {
        /* Unknown applications retain their own icon instead of a misleading stock symbol. */
        canvas_set_color(canvas, ColorBlack);
        canvas_draw_box(canvas, center - 8, top + 18, 16, 16);
        canvas_set_color(canvas, ColorWhite);
        canvas_set_bitmap_mode(canvas, 1);
        canvas_draw_icon_animation(canvas, center - 7, top + 19, item->icon);
        canvas_set_bitmap_mode(canvas, 0);
    }
    if(model->count > 1) {
        const size_t prev = model->position ? model->position - 1 : model->count - 1;
        const size_t next = (model->position + 1) % model->count;
        signal_icon(
            canvas,
            center - 48,
            top + 20,
            1,
            dark_signal_icon_kind(model->items[prev].icon->icon),
            false);
        signal_icon(
            canvas,
            center + 34,
            top + 20,
            1,
            dark_signal_icon_kind(model->items[next].icon->icon),
            false);
        canvas_draw_line(canvas, 3, top + 26, 7, top + 22);
        canvas_draw_line(canvas, 3, top + 26, 7, top + 30);
        canvas_draw_line(
            canvas, canvas_width(canvas) - 4, top + 26, canvas_width(canvas) - 8, top + 22);
        canvas_draw_line(
            canvas, canvas_width(canvas) - 4, top + 26, canvas_width(canvas) - 8, top + 30);
    }
    canvas_set_font(canvas, FontPrimary);
    elements_scrollable_text_line_str(
        canvas,
        center,
        canvas_height(canvas) - 5,
        canvas_width(canvas) - 8,
        item->label,
        model->scroll_counter > 2 ? model->scroll_counter - 2 : 0,
        false,
        true);
    canvas_set_color(canvas, ColorBlack);
}

size_t dark_signal_menu_navigate(const MenuModel* model, InputKey key) {
    if(!model->count) return 0;
    if(key == InputKeyLeft || key == InputKeyUp) {
        return model->position ? model->position - 1 : model->count - 1;
    }
    if(key == InputKeyRight || key == InputKeyDown) return (model->position + 1) % model->count;
    return model->position;
}

void dark_signal_invert(Canvas* canvas) {
    canvas_set_color(canvas, ColorXOR);
    canvas_draw_box(canvas, 0, 0, canvas_width(canvas), canvas_height(canvas));
    canvas_set_color(canvas, ColorBlack);
}

void dark_signal_logo(Canvas* canvas, int32_t x, int32_t y) {
    /* Interlocked DB monogram; drawn on the native pixel grid. */
    static const uint16_t pixels[] = {
        0x7E00, 0xFF00, 0xC380, 0xC180, 0xC180, 0xC180, 0xC180, 0xC180, 0xCFFC, 0xDFFE,
        0xDE06, 0xDC06, 0xFC06, 0xFC0C, 0xDC1C, 0xDC0E, 0x1C06, 0x1C06, 0x1FFE, 0x0FFC,
    };
    for(size_t row = 0; row < COUNT_OF(pixels); row++) {
        for(size_t col = 0; col < 16; col++) {
            if(pixels[row] & (0x8000 >> col)) {
                canvas_draw_box(canvas, x + col * 2, y + row * 2, 2, 2);
            }
        }
    }
}

void dark_signal_settings_icon(Canvas* c, int32_t x, int32_t y, const char* label) {
    if(strstr(label, "Displej") || strstr(label, "LCD") || strstr(label, "Upozor")) {
        canvas_draw_frame(c, x, y + 1, 10, 7);
        canvas_draw_line(c, x + 3, y + 9, x + 7, y + 9);
    } else if(strstr(label, "Zvuk")) {
        canvas_draw_box(c, x, y + 3, 3, 4);
        canvas_draw_line(c, x + 3, y + 3, x + 6, y);
        canvas_draw_line(c, x + 6, y, x + 6, y + 9);
        canvas_draw_line(c, x + 8, y + 2, x + 10, y + 5);
        canvas_draw_line(c, x + 10, y + 5, x + 8, y + 8);
    } else if(strstr(label, "Plocha") || strstr(label, "Desktop")) {
        canvas_draw_line(c, x, y + 4, x + 5, y);
        canvas_draw_line(c, x + 5, y, x + 10, y + 4);
        canvas_draw_frame(c, x + 2, y + 4, 7, 6);
    } else {
        canvas_draw_frame(c, x + 1, y + 1, 8, 8);
        canvas_draw_box(c, x + 4, y + 4, 2, 2);
    }
}

void dark_signal_lock_draw(Canvas* canvas, const char* clock, bool pin_locked, int32_t offset) {
    canvas_set_color(canvas, ColorBlack);
    canvas_draw_box(canvas, 0, 13, 128, 51);
    canvas_set_color(canvas, ColorWhite);
    dark_signal_logo(canvas, 5 + offset, 19);
    canvas_set_font(canvas, FontBigNumbers);
    canvas_draw_str_aligned(canvas, 84, 38, AlignCenter, AlignCenter, clock);
    canvas_set_font(canvas, FontSecondary);
    canvas_draw_str_aligned(
        canvas, 85, 51, AlignCenter, AlignCenter, pin_locked ? "Odemknout: PIN" : "Odemknout");
    canvas_set_font(canvas, FontBatteryPercent);
    canvas_draw_str_aligned(
        canvas, 85, 60, AlignCenter, AlignCenter, pin_locked ? "Stiskni tlacitko" : "3x ZPET");
    canvas_set_color(canvas, ColorBlack);
}
