/** @odoo-module **/

console.log("🚀 dokumenti_tabs_loader.js učitan!");

// -------------------
// Pomoćne funkcije
// -------------------

function loadProjectsTab(showMine) {
    const url = '/portal/projects/snippet' + (showMine ? '?show_mine=true' : '');
    const $projectsContent = $("#projects-tab-content");

    $projectsContent.html("Loading...");
    $projectsContent.load(url, function () {
        if (showMine) {
            $("#filter-mine").hide();
            $("#filter-all").show();
        } else {
            $("#filter-mine").show();
            $("#filter-all").hide();
        }

        $("#filter-mine").off('click').on('click', function () {
            loadProjectsTab(true);
        });

        $("#filter-all").off('click').on('click', function () {
            loadProjectsTab(false);
        });
    });
}

function initTabLoaders() {
    const tabUrls = {
        "nav_tabs_content_info": "/portal/info/snippet",
        "nav_tabs_content_1749017674113_74": "/portal/offers/snippet",
        "nav_tabs_content_1749017674113_75": "/portal/contracts/snippet",
        "nav_tabs_content_1749017674113_76": "/portal/projects/snippet"
    };

    $(".s_tabs_nav a[data-bs-toggle='tab']").on("shown.bs.tab", (e) => {
        const targetId = $(e.target).attr("href").replace("#", "");
        const url = tabUrls[targetId];
        if (url) {
            const $contentDiv = $("#" + targetId).find("> div[id$='-content']");
            if ($contentDiv.length && $contentDiv.html().trim() === "Loading...") {
                $contentDiv.load(url, () => {
                    console.log(`🔄 Učitan sadržaj za tab: ${targetId}`);
                });
            }
        }
    });
}

$(document).ready(function () {
    console.log("✅ DOM spreman. Pokrećem inicijalizaciju.");

    loadProjectsTab(false);
    initTabLoaders();

    $(document).on('click', '#filter-mine', function () {
        loadProjectsTab(true);
    });

    $(document).on('click', '#filter-all', function () {
        loadProjectsTab(false);
    });

    $(document).on('click', '.open-project', function () {
        const isContractor = $(this).data('is-contractor');

        if (!isContractor) {
            $('#projectAccessModal').modal('show');
        } else {
            const projectId = $(this).data('id');
            window.location.href = `/portal/project/tasks_kanban/${projectId}`;
        }
    });

    setTimeout(() => {
        $("form").each(function () {
            $(this).find("button[type='submit']").removeClass("o_website_btn_loading o_website_form_send disabled pe-none");
        });
    }, 1000);
});

