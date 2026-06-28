📌 Overview
VoteGuard is an AI-assisted voter verification system designed to improve the accuracy and transparency of electoral databases. It identifies duplicate, ghost, and inconsistent voter records using rule-based risk analysis and presents the results through an interactive Streamlit dashboard. The project also demonstrates RFID-based voter identity verification using ESP32 and RC522.

✨ Features
🔍 Detects duplicate voter records
👻 Identifies potential ghost voters
🤖 Rule-based AI risk analysis
🚦 Risk classification (Low, Medium, High)
📊 Interactive Streamlit dashboard
🌍 Filter by City, State, and Gender
📥 Download filtered reports
📡 RFID-based voter verification using ESP32 & RC522
🔒 Human-in-the-loop verification (no automatic voting decisions)

🛠️ Tech Stack
Python
Streamlit
Pandas
RapidFuzz
ESP32
RC522 RFID Module
Arduino IDE

⚙️ Workflow
Load voter dataset.
Analyze records for inconsistencies.
Calculate risk score.
Classify records into Low, Medium, or High risk.
Display results in the dashboard.
Verify RFID card (ESP32 + RC522 prototype).
Assist officials in manual verification.
🚀 Future Enhancements
NFC-enabled Voter ID verification
Machine Learning–based anomaly detection
Real-time Election Commission database integration
Secure encrypted voter identity management

📄 License
This project is developed for educational and research purposes.
