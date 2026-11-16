#include <furi.h>
#include <furi_hal.h>
#include <gui/elements.h>
#include <assets_icons.h>

#include "desktop_view_slideshow.h"
#include "../helpers/slideshow.h"

#define DESKTOP_BOOT_LOGO_DURATION 1200
#define DESKTOP_SLIDESHOW_POWEROFF_SHORT 5000
#define DESKTOP_SLIDESHOW_POWEROFF_LONG  (60 * 60 * 1000)

struct DesktopSlideshowView {
    View* view;
    DesktopSlideshowViewCallback callback;
    void* context;
    FuriTimer* timer;
    FuriTimer* boot_timer;
};

typedef struct {
    uint8_t page;
    Slideshow* slideshow;
} DesktopSlideshowViewModel;

static void desktop_view_slideshow_draw(Canvas* canvas, void* model) {
    DesktopSlideshowViewModel* m = model;

    canvas_clear(canvas);
    if(slideshow_is_loaded(m->slideshow)) {
        slideshow_draw(m->slideshow, canvas, 0, 0);
    } else {
        canvas_draw_icon(canvas, 5, 6, &I_DonnyBoy_32x40);
        canvas_set_font(canvas, FontPrimary);
        canvas_draw_str_aligned(canvas, 83, 17, AlignCenter, AlignBottom, "DONNY BOY");
        canvas_set_font(canvas, FontSecondary);
        canvas_draw_str_aligned(canvas, 83, 31, AlignCenter, AlignBottom, "Vitej zpatky");
        canvas_draw_str_aligned(canvas, 83, 42, AlignCenter, AlignBottom, "CZ FIRMWARE");
        canvas_draw_str_aligned(canvas, 64, 59, AlignCenter, AlignBottom, "TVUJ TEMNY SIGNAL.");
    }
}

static bool desktop_view_slideshow_input(InputEvent* event, void* context) {
    furi_assert(event);
    DesktopSlideshowView* instance = context;

    DesktopSlideshowViewModel* model = view_get_model(instance->view);
    bool update_view = false;
    if(event->type == InputTypeShort) {
        bool end_slideshow = false;
        switch(event->key) {
        case InputKeyLeft:
            slideshow_goback(model->slideshow);
            break;
        case InputKeyRight:
        case InputKeyOk:
            end_slideshow = !slideshow_advance(model->slideshow);
            break;
        case InputKeyBack:
            end_slideshow = true;
        default:
            break;
        }
        if(end_slideshow) {
            instance->callback(DesktopSlideshowCompleted, instance->context);
        }
        update_view = true;
    } else if(event->key == InputKeyOk && instance->timer) {
        if(event->type == InputTypePress) {
            furi_timer_start(instance->timer, DESKTOP_SLIDESHOW_POWEROFF_SHORT);
        } else if(event->type == InputTypeRelease) {
            furi_timer_stop(instance->timer);
            /*if(!slideshow_is_one_page(model->slideshow)) {
                furi_timer_start(instance->timer, DESKTOP_SLIDESHOW_POWEROFF_LONG);
            }*/
        }
    }
    view_commit_model(instance->view, update_view);

    return true;
}

static void desktop_first_start_timer_callback(void* context) {
    DesktopSlideshowView* instance = context;
    instance->callback(DesktopSlideshowPoweroff, instance->context);
}

static void desktop_boot_logo_timer_callback(void* context) {
    DesktopSlideshowView* instance = context;
    instance->callback(DesktopSlideshowCompleted, instance->context);
}

static void desktop_view_slideshow_enter(void* context) {
    DesktopSlideshowView* instance = context;

    furi_assert(instance->timer == NULL);
    instance->timer =
        furi_timer_alloc(desktop_first_start_timer_callback, FuriTimerTypeOnce, instance);

    DesktopSlideshowViewModel* model = view_get_model(instance->view);
    model->slideshow = slideshow_alloc();
    if(!slideshow_load(model->slideshow, SLIDESHOW_FS_PATH)) {
        instance->boot_timer =
            furi_timer_alloc(desktop_boot_logo_timer_callback, FuriTimerTypeOnce, instance);
        furi_timer_start(instance->boot_timer, DESKTOP_BOOT_LOGO_DURATION);
    } else if(!slideshow_is_one_page(model->slideshow)) {
        furi_timer_start(instance->timer, DESKTOP_SLIDESHOW_POWEROFF_LONG);
    }
    view_commit_model(instance->view, false);
}

static void desktop_view_slideshow_exit(void* context) {
    DesktopSlideshowView* instance = context;

    if(instance->boot_timer) {
        furi_timer_stop(instance->boot_timer);
        furi_timer_free(instance->boot_timer);
        instance->boot_timer = NULL;
    }
    furi_timer_stop(instance->timer);
    furi_timer_free(instance->timer);
    instance->timer = NULL;

    DesktopSlideshowViewModel* model = view_get_model(instance->view);
    slideshow_free(model->slideshow);
    view_commit_model(instance->view, false);
}

DesktopSlideshowView* desktop_view_slideshow_alloc(void) {
    DesktopSlideshowView* instance = malloc(sizeof(DesktopSlideshowView));
    instance->boot_timer = NULL;
    instance->timer = NULL;
    instance->view = view_alloc();
    view_allocate_model(instance->view, ViewModelTypeLocking, sizeof(DesktopSlideshowViewModel));
    view_set_context(instance->view, instance);
    view_set_draw_callback(instance->view, (ViewDrawCallback)desktop_view_slideshow_draw);
    view_set_input_callback(instance->view, desktop_view_slideshow_input);
    view_set_enter_callback(instance->view, desktop_view_slideshow_enter);
    view_set_exit_callback(instance->view, desktop_view_slideshow_exit);

    return instance;
}

void desktop_view_slideshow_free(DesktopSlideshowView* instance) {
    furi_assert(instance);

    view_free(instance->view);
    free(instance);
}

View* desktop_view_slideshow_get_view(DesktopSlideshowView* instance) {
    furi_assert(instance);
    return instance->view;
}

void desktop_view_slideshow_set_callback(
    DesktopSlideshowView* instance,
    DesktopSlideshowViewCallback callback,
    void* context) {
    furi_assert(instance);
    furi_assert(callback);
    instance->callback = callback;
    instance->context = context;
}
