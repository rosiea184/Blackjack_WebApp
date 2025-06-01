import random
#from flask import session

class Card:
    def __init__(self, value, suit):
        self.value = value
        self.suit = suit

    def __str__(self):
        return f"{self.value} of {self.suit}"

def card_from_string(card_str):
    # Example input: "Ace of Spades"
    parts = card_str.split(" of ")
    if len(parts) != 2:
        raise ValueError(f"Invalid card format: {card_str}")
    value, suit = parts
    return Card(value, suit)


class Deck:
    def __init__(self):
        self.cards = self.generate_deck()
        self.shuffle_deck()

    def generate_deck(self):
        suits = ["Hearts", "Diamonds", "Clubs", "Spades"]
        faces = ["Ace", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Jack", "Queen", "King"]
        return [Card(value, suit) for suit in suits for value in faces]

    def shuffle_deck(self):
        if len(self.cards) == 52:
            random.shuffle(self.cards)
        else:
            print("Cards are missing")

    def deal_card(self):
        return self.cards.pop(0) if self.cards else None

class Player:
    def __init__(self, hand=None):
        self.hand = hand if hand is not None else []
        self.score = 0
        self.turn = True

    def hit(self, deck):
        self.hand.append(deck.deal_card())

    def calculate_score(self):
        score = 0
        for card in self.hand:
            if card.value == "Ace":
                score += 11 if score < 11 else 1
            elif card.value in ["Ten", "Jack", "Queen", "King"]:
                score += 10
            else:
                score += ["Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"].index(card.value) + 2
        self.score = score
        return score

class Dealer(Player):
    def __init__(self, hand=None):
        super().__init__(hand)
        self.stay = False

def init_deal(dealer, player, deck):
    for _ in range(2):
        dealer.hand.append(deck.deal_card())
        player.hand.append(deck.deal_card())

def get_game_result(player_score, dealer_score, player_hand):
    if player_score == dealer_score:
        result = 'tie'
    elif player_score > 21:
        result = 'loss'
    elif dealer_score > 21 or player_score > dealer_score:
        result = 'win'
    elif player_score < dealer_score:
        result = 'loss'
    elif player_score == 21 and len(player_hand) == 2:
        result = 'blackjack'
    
    return result


def blackjack_round(action=None, session=None):
    if session is None:
        raise ValueError("Session object must be passed to blackjack_round")
    
    # Initialize game components
    if 'deck' not in session:
        deck = Deck()
        dealer = Dealer()
        player = Player()
        init_deal(dealer, player, deck)
        # Calculate scores immediately after dealing
        player.calculate_score()
        dealer.calculate_score()

        session['deck'] = [str(card) for card in deck.cards]
        session['player_hand'] = [str(card) for card in player.hand]
        session['dealer_hand'] = [str(card) for card in dealer.hand]

        # Check player blackjack first (player wins instantly)
        if player.score == 21 and len(player.hand) == 2 and dealer.score != 21:
            session['game_over'] = True
            result = 'blackjack'
        # If player doesn't have blackjack, check dealer blackjack (player loses instantly)
        elif dealer.score == 21 and len(dealer.hand) == 2:
            session['game_over'] = True
            result = 'loss'
        else:
            session['game_over'] = False
            result = None
    else:
        deck = Deck()
        deck.cards = [card_from_string(c) for c in session['deck']]
        player = Player([card_from_string(c) for c in session['player_hand']])
        dealer = Dealer([card_from_string(c) for c in session['dealer_hand']])
        # Calculate initial scores from loaded hands
        player.calculate_score()
        dealer.calculate_score()
        result = None  # default if continuing game

 # Player's turn
    if not session.get('game_over'):
        if action == 'hit':
            player.hit(deck)
            session['player_hand'] = [str(card) for card in player.hand]
        elif action == 'stand':
            session['game_over'] = True

        player.calculate_score()
        session['deck'] = [str(card) for card in deck.cards]

        if player.score > 21:
            session['game_over'] = True

    # Dealer's turn if game is over
    if session.get('game_over'):
        if result is None:
            # Dealer only draws if player hasn't busted
            if player.score <= 21:
                dealer.calculate_score()
                while dealer.score < 17:
                    dealer.hit(deck)
                    dealer.calculate_score()
            # Calculate result after dealer plays or if player busted
            result = get_game_result(player.score, dealer.score, player.hand)
    else:
        result = None

    # Save updated state
    session['deck'] = [str(card) for card in deck.cards]
    session['player_hand'] = [str(card) for card in player.hand]
    session['dealer_hand'] = [str(card) for card in dealer.hand]

    return {
        'player_hand': [str(card) for card in player.hand],
        'dealer_hand': [str(card) for card in dealer.hand],
        'player_score': player.score,
        'dealer_score': dealer.score,
        'result': result
        }
