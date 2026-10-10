// CATCH — main.js
document.addEventListener("DOMContentLoaded", function () {

    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll(".alert").forEach(function (alertEl) {
        setTimeout(function () {
            const alert = bootstrap.Alert.getOrCreateInstance(alertEl);
            alert.close();
        }, 5000);
    });

    // Image upload preview (used on report-lost / report-found / profile forms)
    document.querySelectorAll(".image-upload-input").forEach(function (input) {
        input.addEventListener("change", function (e) {
            const preview = document.querySelector(input.dataset.previewTarget);
            if (!preview) return;
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function (ev) {
                    preview.src = ev.target.result;
                    preview.classList.remove("d-none");
                };
                reader.readAsDataURL(file);
            }
        });
    });

    // Simple client-side search/filter for item listing tables
    const searchInput = document.getElementById("itemSearchInput");
    if (searchInput) {
        searchInput.addEventListener("input", function () {
            const query = searchInput.value.toLowerCase();
            document.querySelectorAll(".searchable-row").forEach(function (row) {
                row.style.display = row.textContent.toLowerCase().includes(query) ? "" : "none";
            });
        });
    }

    // Animate match score rings on the match results page
    document.querySelectorAll(".match-score-ring").forEach(function (ring) {
        const score = parseFloat(ring.dataset.score || "0");
        if (score >= 70) {
            ring.classList.add("score-high");
        } else if (score >= 45) {
            ring.classList.add("score-mid");
        } else {
            ring.classList.add("score-low");
        }
    });
});
