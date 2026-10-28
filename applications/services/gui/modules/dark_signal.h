#pragma once

#include <gui/canvas.h>
#include <gui/modules/menu.h>

/* Built into the shell so the default theme does not depend on a loader .fal. */
void dark_signal_menu_draw(Canvas* canvas, MenuModel* model);
size_t dark_signal_menu_navigate(const MenuModel* model, InputKey key);
void dark_signal_invert(Canvas* canvas);
void dark_signal_logo(Canvas* canvas, int32_t x, int32_t y);
void dark_signal_lock_draw(Canvas* canvas, const char* clock, bool pin_locked, int32_t offset);
void dark_signal_settings_icon(Canvas* canvas, int32_t x, int32_t y, const char* label);
