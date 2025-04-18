# 機會命運卡牌

import random

class Chance:
    def __init__(self, 
                 card: str,
                 lost: int = 0,
                 gain: int = 0,
                 move: int = 0):
        self.card = card
        self.lost = lost
        self.gain = gain
        self.move = move

def get_chance_card() -> Chance:
    cards = [
        Chance("獲得$100獎金", gain=100),
        Chance("獲得$50獎金", gain=50),
        Chance("繳交$30罰款", lost=30),
        Chance("繳交$75罰款", lost=75),
        Chance("獲得$200獎金", gain=200),
        Chance("繳交$100罰款", lost=100),
        Chance("獲得$150獎金", gain=150),
        Chance("繳交$20罰款", lost=20),
    ]
    return random.choice(cards)