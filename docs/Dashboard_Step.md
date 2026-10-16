# The forecast screen is ready

Open http://127.0.0.1:8765 while the local service is running. See [the setup guide](Reproduce.md) to start the service.

1. Choose a 4G or 5G station and sector. A sector is one part of a station's radio coverage.
2. Choose a recorded date and time. All times on this screen use UTC.
3. Click **Show forecast**. The button shows **Calculating…**, then a confirmation identifies the sector and UTC time displayed. Changing a selection leaves the previous results in place until the button is pressed. The opening example loads automatically; the time-navigation buttons also load their selected moment.
4. Read the three cards: predictions for 15, 30 and 60 minutes later. Each also shows a lower and upper estimate, and the later actual reading when available.

At the opening example (4G, Site 16, sector 1, 26 April 2025 at 00:00 UTC), the 60-minute prediction is **16.91%**. The actual reading at 01:00 was **13.78%**. The difference is **3.13 percentage points**, calculated by subtracting the two percentages. This is one example, not the average performance of the model.

Use the missing-readings selector to hide recent inputs in a simulation. With the latest 30 minutes hidden, the service reuses the last available reading and withholds ranges. With the latest 90 minutes hidden, it gives no estimate. Original measurements and later actual answers stay intact.

The chart shows six hours of recorded past and one hour after the chosen moment. Blank observations remain gaps. Green dots are predictions; vertical green bars are ranges. Brown readings after the forecast moment are shown only to check the predictions. Uncheck “Show later actual readings” to hide those answers.

## Where this fits

Original ZIP → clean observations → training examples → trained models → prediction service → **this screen**.

| File | Why it exists |
|---|---|
| `networkprb/static/index.html` | Screen text and controls |
| `networkprb/static/style.css` | Layout and colours |
| `networkprb/static/app.js` | Sends selected past history to the service and draws the results |
| `networkprb/replay.py` | Reads saved observations; separates past model inputs from later display answers |
| `networkprb/api.py` | Serves the screen and prediction requests on this computer |
| `outputs/dashboard_v1/` | Saved HTTP check evidence and screenshot |

No new models were trained. Existing models, calibration adjustments and missing-reading rules were reused. All 41 automated tests passed. The HTTP smoke check also exercised all 20 sector series. Browser checks exercised sector selection, time navigation, missing-input scenarios and actual-reading visibility.

This is historical replay, not a live network connection. Ranges are not guaranteed; missing inputs can reduce their reliability. The selected final-test cohort has no readings at or above 80%, so this project cannot yet claim validated high-load warnings.

See [the project overview](START_HERE.md) and [reproduction instructions](Reproduce.md) for the complete workflow.

For restarting later, the PowerShell command from the project folder is:

```powershell
.\.venv\Scripts\python.exe -m networkprb.api --port 8765
```

Expected output: `NetworkPRB historical replay API: http://127.0.0.1:8765`. Open that address. Keep the terminal running while using the screen.
