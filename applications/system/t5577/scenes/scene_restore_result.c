#include "../t5577_app.h"
#include <t5577_icons.h>

void t5577_app_scene_restore_result_on_enter(void* context) {
    T5577App* app = context;

    const bool answered = t5577_config_found(&app->config);
    // Nothing read back is nothing proven, whatever the counters say - and a run whose only
    // verified blocks were refused traceability words proved nothing either, however correct
    // that refusal was.
    const bool restored = answered && app->checked > app->bad_trace && app->bad == 0 &&
                          app->lost == 0;

    popup_reset(app->popup);

    if(restored) {
        popup_set_header(app->popup, "Zapsano!", 75, 10, AlignLeft, AlignTop);
        popup_set_icon(app->popup, 0, 9, &I_DolphinSuccess_91x55);
        // Said rather than left out: the dump no longer matches the tag block for block, and
        // the user is owed the reason before they go looking for a fault.
        if(app->bad_trace > 0) {
            popup_set_text(app->popup, "P1 stopa\nbeze zmeny", 75, 26, AlignLeft, AlignTop);
        }
        notification_message(app->notifications, &sequence_success);
    } else {
        popup_set_header(app->popup, "Nezapsano", 64, 4, AlignCenter, AlignTop);

        // Which failure it was decides what to do about it, so the screen says which. A tag
        // that stopped answering is worth another go; a block that read back different is a
        // write the chip refused - a locked block, or the wrong password - and naming the
        // block is the only way to tell which one that was.
        if(!answered) {
            // "Wrote" would be a claim about the tag, and this is the one branch with no
            // evidence from it at all: a write frame has no answer, so the count is frames
            // sent. Nothing says whether a tag took any of them - or was ever there. Which of
            // the three ways it got here decides what to do about it, so it is named - and no
            // default, so a fourth reason is a build failure rather than a wrong sentence.
            switch(app->read_back) {
            case T5577RestoreReadBackNoWord:
                snprintf(
                    app->progress,
                    sizeof(app->progress),
                    "Cip vyzaduje heslo,\nktere vypis nema");
                break;
            case T5577RestoreReadBackSent:
                // The one case where something went out that cannot be taken back. Said plainly,
                // because the tag may have been open and the frame is then a write.
                snprintf(
                    app->progress,
                    sizeof(app->progress),
                    "Heslo odeslano,\nbez odpovedi. Over\nblok 0");
                break;
            case T5577RestoreReadBackSilent:
                snprintf(
                    app->progress,
                    sizeof(app->progress),
                    "Odeslano %u bloku,\nbez odpovedi",
                    app->done);
                break;
            }
        } else if(app->checked == 0) {
            snprintf(app->progress, sizeof(app->progress), "Vypis neobsahuje\ndata k zapisu");
        } else if(app->bad == 0 && app->lost == 0) {
            // Every block checked was a traceability word that came back unchanged. Reported as
            // a failure because nothing was proven, not because the chip did anything wrong.
            snprintf(app->progress, sizeof(app->progress), "Jen P1 stopa,\nktera se nemeni");
        } else if(app->lost > 0 && app->bad > 0) {
            // Both happened, so both get said: the counts are what distinguish a tag that
            // moved from blocks the chip refused, and one of them alone would be a diagnosis
            // of the wrong thing.
            snprintf(
                app->progress,
                sizeof(app->progress),
                "Ztracen cip P%ub%u,\n%u rozdilu",
                app->lost_at.page,
                app->lost_at.block,
                app->bad);
        } else if(app->lost > 0) {
            snprintf(
                app->progress,
                sizeof(app->progress),
                "Ztracen cip na\nP%u blok %u",
                app->lost_at.page,
                app->lost_at.block);
        } else {
            snprintf(
                app->progress,
                sizeof(app->progress),
                "P%u blok %u se lisi\n(%u z %u)",
                app->bad_at.page,
                app->bad_at.block,
                app->bad,
                app->checked);
        }
        popup_set_text(app->popup, app->progress, 64, 22, AlignCenter, AlignTop);
        notification_message(app->notifications, &sequence_error);
    }

    view_dispatcher_switch_to_view(app->view_dispatcher, T5577AppViewPopup);
}

bool t5577_app_scene_restore_result_on_event(void* context, SceneManagerEvent event) {
    T5577App* app = context;

    // Back leaves the write behind rather than returning into it: the restore scene writes the
    // tag on entry, so stepping back into it would write the tag again.
    if(event.type != SceneManagerEventTypeBack) return false;

    if(!scene_manager_search_and_switch_to_previous_scene(
           app->scene_manager, T5577AppSceneFileMenu)) {
        scene_manager_search_and_switch_to_previous_scene(app->scene_manager, T5577AppSceneStart);
    }

    return true;
}

void t5577_app_scene_restore_result_on_exit(void* context) {
    T5577App* app = context;
    popup_reset(app->popup);
}
