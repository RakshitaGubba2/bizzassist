/* Language switcher only — UI translation happens server-side before the page is sent. */
(function () {
    'use strict';

    function currentLanguage() {
        return document.body.dataset.currentLanguage || window.CURRENT_LANGUAGE || 'en';
    }

    window.toggleLanguageSwitcher = function () {
        const panel = document.getElementById('languagePanel');
        if (!panel) return;
        panel.classList.toggle('open');
        panel.setAttribute('aria-hidden', panel.classList.contains('open') ? 'false' : 'true');
        if (!panel.childElementCount) buildLanguagePanel(panel);
    };

    function buildLanguagePanel(panel) {
        const entries = window.SUPPORTED_LANGUAGES || {};
        Object.entries(entries).forEach(([code, label]) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = label + (code === currentLanguage() ? ' ✓' : '');
            button.addEventListener('click', () => window.setLanguage(code));
            panel.appendChild(button);
        });
    }

    window.setLanguage = function (language) {
        try {
            localStorage.setItem('language', language);
        } catch (e) {}
        fetch('/set-language', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language }),
        })
            .then((response) => response.json())
            .then((data) => {
                if (data && data.status === 'ok') window.location.reload();
            })
            .catch(() => window.location.reload());
    };

    window.setReplyLanguage = function (language) {
        try {
            localStorage.setItem('reply_language', language);
        } catch (e) {}
        fetch('/set-reply-language', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reply_language: language }),
        }).catch(() => {});
    };

    document.addEventListener('DOMContentLoaded', function () {
        try {
            const stored = localStorage.getItem('language');
            if (stored && stored !== currentLanguage()) {
                window.setLanguage(stored);
            }
        } catch (e) {}
    });
})();
