from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from blackjack_game import blackjack_round
from functools import wraps
import boto3, json, os, logging, uuid, re

logging.basicConfig(level=logging.INFO, filename='app.log', format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
db_user = os.environ.get('DB_USER')
db_pass = os.environ.get('DB_PASSWORD')
db_host = os.environ.get('DB_HOST')
db_name = os.environ.get('DB_NAME')

def get_db_secret(secret_name, region_name='us-east-1'):
    client = boto3.client('secretsmanager', region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    secret = get_secret_value_response['SecretString']
    return json.loads(secret)

#fetch credentials from AWS Secrets Manager
secret = get_db_secret('prod/rds/mydb')

basedir = os.path.abspath(os.path.dirname(__name__))
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{secret['username']}:{secret['password']}@{secret['host']}/{secret['dbname']}" 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'
db = SQLAlchemy(app)
BUCKET_NAME = 'flask-todo-bucket'

def upload_to_s3(file_path, s3_key):
    s3 = boto3.client('s3')
    try:
        logging.info(f"Attempting to upload {file_path} to bucket {BUCKET_NAME} as {s3_key}")
        s3.upload_file(file_path, BUCKET_NAME, s3_key)
        logging.info(f"Uploaded {file_path} to S3 bucket {BUCKET_NAME} with key {s3_key}.")
        return f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
    except Exception as e:
        logging.error(f"Error uploading file to S3: {e}")
        return None

# Clean filename to remove unsafe characters
def safe_filename(filename):
    name, ext = os.path.splitext(filename)
    name = re.sub(r'[^\w\-_.]', '_', name)  # Replace unsafe chars
    return f"{uuid.uuid4()}_{name}{ext}"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('player_id'):
            flash("Please log in to access this page.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

class player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    profile_picture = db.Column(db.String(200), nullable=True)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    blackjacks = db.Column(db.Integer, default=0)
    ties = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"Player('{self.name}', '{self.wins}', '{self.losses}', '{self.blackjacks}', '{self.ties}')"

@app.route('/')
def index():
    player_id = session.get('player_id')
    player_name = session.get('player_name')
    current_player = db.session.get(player, player_id) if player_id else None
    return render_template('index.html', player=current_player)

@app.route('/register', methods=['POST', 'GET'])
def register():
    error = None
    if request.method == 'POST':
        player_name = request.form.get('username')
        password = request.form.get('password')

        # Check if player already exists
        existing_player = player.query.filter_by(name=player_name).first()
        if existing_player:
            error = "Username already taken. Please choose another."
        else:
            # Hash the password
            hashed_password = generate_password_hash(password)
            new_player = player(name=player_name, password_hash=hashed_password)

            # Handle profile picture upload
            try:
                file = request.files.get('profile_picture')
            except Exception as e:
                logging.error(f"Error retrieving file: {e}")
                file = None

            if file:
                unique_filename = safe_filename(file.filename)
                file_path = os.path.join(basedir, unique_filename)
                file.save(file_path)
                s3_url = upload_to_s3(file_path, unique_filename)
                os.remove(file_path)

                if s3_url:
                    new_player.profile_picture = s3_url
                    print(new_player.profile_picture)
                    logging.info(f"File uploaded to S3: {s3_url}")
            else:
                logging.info("No file received.")

            # Now add to DB and commit once
            db.session.add(new_player)
            db.session.commit()
            session['player_id'] = new_player.id
            session['player_name'] = new_player.name
            return redirect(url_for('blackjack'))

    return render_template('register.html', error=error)


@app.route('/login', methods=['POST', 'GET']) 
def login():
    error = None
    if request.method == 'POST':
        # Handle form submission and login player
        player_name = request.form.get('username')
        password = request.form.get('password')
        existing_player = player.query.filter_by(name=player_name).first()
        if not existing_player:
            error = "Username not found. Please register first."
        elif not check_password_hash(existing_player.password_hash, password):
            error = "Incorrect password. Please try again."
        else:
            session['player_id'] = existing_player.id
            session['player_name'] = existing_player.name
            return redirect(url_for('blackjack'))
    elif 'forgot_password_submit' in request.form:
            # User clicked the Forgot Password button, show the forgot password form
            show_forgot_password = True
    return render_template('login.html', error=error, show_forgot_password=show_forgot_password)

@app.route('/profile')
@login_required
def profile():
    player_id = session.get('player_id')
    current_player = db.session.get(player, player_id)
    return render_template('profile.html', player=current_player)

@app.route('/update_picture', methods=['POST'])
@login_required
def update_picture():
    player_id = session.get('player_id')

    current_player = db.session.get(player, player_id)
    file = request.files.get('file')

    if file:
        ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{ext}"
        file_path = os.path.join(basedir, unique_filename)
        file.save(file_path)

        s3_url = upload_to_s3(file_path, unique_filename)
        os.remove(file_path)

        if s3_url:
            current_player.profile_picture = s3_url
            db.session.commit()
            logging.info(f"Updated profile picture: {s3_url}")
        else:
            logging.error("Failed to upload new profile picture.")
    else:
        logging.info("No new picture uploaded.")

    return redirect(url_for('profile'))

@app.route('/blackjack', methods=['POST', 'GET'])
@login_required
def blackjack():
    player_id = session.get('player_id')
    current_player = db.session.get(player, player_id)
    action = request.form.get('action') if request.method == 'POST' else None

    game_state = blackjack_round(action, session)  # Call imported function

    # Update stats
    if game_state['result']:
        if game_state['result'] == 'win':
            current_player.wins += 1
        elif game_state['result'] == 'loss':
            current_player.losses += 1
        elif game_state['result'] == 'blackjack':
            current_player.wins += 1
            current_player.blackjacks += 1
        elif game_state['result'] == 'tie':
            current_player.ties += 1   
        db.session.commit()

    return render_template(
        'blackjack.html',
        player_hand=game_state['player_hand'],
        dealer_hand=game_state['dealer_hand'],
        player_score=game_state['player_score'],
        dealer_score=game_state['dealer_score'],
        result=game_state['result'],
        player=current_player
    )
@app.route('/blackjack/reset')
def reset_blackjack():
    session.pop('deck', None)
    session.pop('player_hand', None)
    session.pop('dealer_hand', None)
    session.pop('game_over', None)
    return redirect(url_for('blackjack'))

@app.route('/scoreboard', methods=['POST', 'GET'])
@login_required
def scoreboard():
    player_id = session.get('player_id')
    if not player_id:
        return redirect(url_for('login'))
    if request.method == 'POST':
        # Handle form submission and update scoreboard
        player_name = request.form.get('name')
        player_score = request.form.get('score')
        new_player = player(name=player_name, score=player_score)
        db.session.add(new_player)
        db.session.commit()
        return redirect(url_for('scoreboard'))
    players = player.query.all()
    return render_template('scoreboard.html', players=players)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        player_name = request.form.get('username')
        existing_player = player.query.filter_by(name=player_name).first()
        
        if existing_player:
            # For now, just display the password (or hashed password, if you want)
            # WARNING: Displaying passwords like this is NOT secure and only for development/testing
            
            # You could decrypt or store plain text password if you had it, 
            # but since you store hashed passwords, just say "Password reset feature coming soon"
            # Or if you have plaintext (not recommended), you could show it here.
            
            # For now, let's just display a fake "password reset link" message.
            
            # Future email send code (commented):
            # reset_token = str(uuid.uuid4())
            # existing_player.reset_token = reset_token
            # existing_player.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            # db.session.commit()
            # send_password_reset_email(existing_player.email, reset_token)
            session['reset_username'] = player_name
            return redirect(url_for('reset_password'))

        else:
            error = "Username not found. Please try again."
            return render_template('login.html', error=error)
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    reset_username = session.get('reset_username')
    if not reset_username:
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            error = "Passwords do not match."
            return render_template('reset_password.html', error=error)

        player_to_update = player.query.filter_by(name=reset_username).first()
        if player_to_update:
            player_to_update.password_hash = generate_password_hash(new_password)
            db.session.commit()
            session.pop('reset_username', None)
            return "Password reset successful! You can now <a href='/login'>log in</a>."
        else:
            return "User not found. Please try again."

    return render_template('reset_password.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', debug=True)