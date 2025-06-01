from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from blackjack_game import blackjack_round
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
    return render_template('index.html')

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
                file = request.files.get('file')
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
        if existing_player and check_password_hash(existing_player.password_hash, password):
            session['player_id'] = existing_player.id  # 👈 Save to session
            return redirect(url_for('blackjack'))
        else:
            error = "Player not found or incorrect password. Please register first."
    return render_template('login.html', error=error)

@app.route('/profile')
def profile():
    player_id = session.get('player_id')
    current_player = db.session.get(player, player_id)
    return render_template('profile.html', player=current_player)

@app.route('/blackjack', methods=['POST', 'GET'])
def blackjack():
    player_id = session.get('player_id')
    if not player_id:
        return redirect(url_for('index'))
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
def scoreboard():
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', debug=True)