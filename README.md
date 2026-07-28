# codex2
An AI-powered Smart Business Assistant designed to help small businesses improve efficiency, decision-making, and growth without requiring technical expertise

## Translation deployment

UI localization is rendered server-side from SQLite and never calls NVIDIA NIM
while serving a page. Populate the versioned UI catalogue before deploying a
new or changed interface:

```powershell
python manage.py prewarm-translations
```

To resume or rebuild one language only, use for example:

```powershell
python manage.py prewarm-translations --language te
```
