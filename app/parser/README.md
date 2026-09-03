# Offline corpus pipeline

Gesetze Parser und Cleaning

```bash
python app/parser/fetch_law.py
python app/parser/clean.py
```

| Script         | Role                                      |
| -------------- | ----------------------------------------- |
| `fetch_law.py` | Download HTML from gesetze-im-internet.de |
| `clean.py`     | Text extrahieren                          |
