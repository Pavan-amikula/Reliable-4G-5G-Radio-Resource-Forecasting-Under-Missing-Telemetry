# Quick start

From the project root in PowerShell, start the local service:

```powershell
.\.venv\Scripts\python.exe -m networkprb.api --port 8765
```

Open http://127.0.0.1:8765. Select a network sector and recorded UTC time to view forecasts and later actual readings. Keep the terminal running; stop with Ctrl+C.

The included models and processed data are ready to use. No retraining or dataset download is required. For environment creation, validation and experiment reproduction, see [Reproduce.md](Reproduce.md).

- [Project overview and architecture](START_HERE.md)
- [Dashboard walkthrough](Dashboard_Step.md)
- [Dataset and baseline results](Stage_1_Results.md)
- [Completed experiments and limitations](Project_Progress.md)
