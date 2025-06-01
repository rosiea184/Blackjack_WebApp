# Blackjack_WebApp
A fun web app to play blackjack and see your scores against other players.
## Table of Contents
   1. [Introduction](#introduction)
   2. [Features](#features)
   3. [Installation](#installation)
## Introduction
   Play Blackjack against the dealer and compare your wins and losses against other players! Log in with your own unique account and play to your heart's content

   This app uses Flask for the backend, MySQL for data storage, and EC2 for hosting.
## Features
   - User Authentication System
      - Secure registration and login functionality
      - Password Protection
      - Home page and navigation changes depending on whether logged in or not.
   - Profile Image Upload
      - Upload a photo during registration
      - Change photo on home page when logged in
      - Photo shows on Home and Blackjack game
   - Blackjack Game
     - Full working blackjack game that tracks how many wins, losses, ties, and blackjacks a user got
   - Scoreboard
     - Shows users stats against other players

## Installation
1. Clone the repository:
   
```bash
  git clone https://github.com/rosiea184/Blackjack_WebApp.git
```

2. Create a virtual environment:

    ```bash
    python3 -m venv venv      # On Windows use python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3. Install required dependencies:

    ```bash
    pip install -r requirements.txt
    ```
4. Update Database and Bucket:
   In app.py you can either update
   ```bash
   secret = get_db_secret('YOURSECRECTNAME')
   ```
   or
   Comment out def get_db_secret and use
   ```bash
   app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
   ```
   instead of
   ```bash
   app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{secret['username']}:{secret['password']}@{secret['host']}/{secret['dbname']}"
   ```
   
5. Run the application:

    ```bash
    python app.py #for Windows
    ```
   ```bash
    python3 app.py
    ```

The app should now be accessible at `[http://localhost:5000](http://127.0.0.1:5000/)`.
