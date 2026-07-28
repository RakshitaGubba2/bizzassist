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
<img width="1497" height="716" alt="Screenshot 2026-07-28 223308" src="https://github.com/user-attachments/assets/7b404bdb-74ab-4c7a-9ec1-c8d7e2bf59c3" />
<img width="1497" height="716" alt="Screenshot 2026-07-28 223241" src="https://github.com/user-attachments/assets/bbd644c0-621e-4171-abb7-f0dc03c00e43" />
<img width="1497" height="712" alt="Screenshot 2026-07-28 223156" src="https://github.com/user-attachments/assets/3066dfe3-0d32-4998-aa70-a903afb9afc0" />
<img width="1495" height="725" alt="Screenshot 2026-07-28 223119" src="https://github.com/user-attachments/assets/4527f93b-26a6-46a5-929f-71af29448735" />
<img width="1482" height="717" alt="Screenshot 2026-07-28 223040" src="https://github.com/user-attachments/assets/985ff1ab-2cbf-4969-851e-2d123331ca15" />
<img width="1512" height="728" alt="Screenshot 2026-07-28 222940" src="https://github.com/user-attachments/assets/3e4e9a1e-315b-445c-b9b3-d5b8b6f30d27" />
<img width="1496" height="717" alt="Screenshot 2026-07-28 222908" src="https://github.com/user-attachments/assets/f102c9b8-d9b5-4b48-801d-23040eafa95d" />
<img width="1511" height="707" alt="Screenshot 2026-07-28 222823" src="https://github.com/user-attachments/assets/5b09f1c6-7c10-49aa-9e3f-5a9016aa7c8d" />
<img width="1511" height="717" alt="Screenshot 2026-07-28 222313" src="https://github.com/user-attachments/assets/057ec75d-a2e9-4436-b1ab-6c23dce65327" />
<img width="1507" height="716" alt="Screenshot 2026-07-28 222034" src="https://github.com/user-attachments/assets/8e3d5129-c3b8-460a-8a25-c6fde3040645" />
<img width="1491" height="735" alt="Screenshot 2026-07-28 221831" src="https://github.com/user-attachments/assets/4fec40df-2772-4eb0-ae77-31f2f6dd638a" />
