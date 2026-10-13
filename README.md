# Blockchain-Based E-Voting System

## About the Project
This is an academic web application developed to explore electronic voting and blockchain concepts using Python and web technologies. It includes voter registration, authentication, vote submission, video recording, and result viewing.

## Technologies Used
- Python
- Flask
- Flask-SQLAlchemy
- SQLite
- HTML, CSS, and JavaScript
- JSON and SHA-256 hashing

## Features
- **Voter Registration:** Register voters using their details and an identity-card image.
- **Voter Authentication:** Demonstrate voter login and OTP verification.
- **Electronic Voting:** Submit a vote through the web interface.
- **Video Recording:** Record and save video during the voting process.
- **Result Viewing:** View vote counts by candidate on the results page.
- **Hash-Linked Records:** Store vote records with hashes linked to previous records and provide an integrity-checking feature.
- **Admin Dashboard:** Review registered voter details and saved identity images and video recordings.

## Project Structure

```text
blockchain-e-voting-system/
│
├── app.py
├── blockchain.json
├── requirements.txt
├── README.md
│
├── adhaarcardphoto/
│   └── Sample identity-card images
│
├── instance/
│   └── evoting.db
│
├── static/
│   ├── logo.png
│   └── styles.css
│
├── templates/
│   ├── admins.html
│   ├── admin_login.html
│   ├── dashboard.html
│   ├── login.html
│   ├── register.html
│   ├── result.html
│   ├── voting_page.html
│   └── party/
│
└── video_records/
    └── Sample video recordings
```

*Note: The structure above is based on the project files. The database, JSON file, and sample uploads may change as the application runs.*

## How to Run on Windows

### Prerequisites
- Python 3.10 or later
- Command Prompt (CMD)

### Steps

1. Download the project ZIP from GitHub and extract it.
2. Open the extracted project folder.
3. Click the folder's address bar, type `cmd`, and press **Enter**. Command Prompt will open in that folder.
4. Install the required dependencies by running:

   ```bash
   python -m pip install -r requirements.txt
   ```

5. Start the application:

   ```bash
   python app.py
   ```

6. Open the local URL displayed in CMD, usually:

   `http://127.0.0.1:5000`

7. Use the application in your browser.

## Documentation
The project report provides additional information about the project objectives, workflow, technologies, and implementation.

## Purpose and Limitations
This project was developed for academic and educational purposes to explore web application development, electronic voting workflows, and hash-linked records. It is a prototype and is not intended for real elections.

## Author
Fareedhul Farzana N
