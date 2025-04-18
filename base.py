from typing import Dict, List
from enum import Enum, auto

from game_setting import *


class SquareType(Enum):
    PROPERTY = auto()
    CHANCE = auto()
    JAIL = auto()
    START = auto()


class Square:
    def __init__(self, 
                 name: str, 
                 color: str = None,
                 price: int = None, 
                 tolls: list = None, 
                 house_cost: int = None):
        
        # base info
        self.name = name
        self.position = 0  # 棋盤位置 初始化統一設定
        if name == "起點":
            self.type: SquareType = SquareType.START
        elif name == "監獄":
            self.type: SquareType = SquareType.JAIL
        elif name in ["機會", "命運"]:
            self.type: SquareType = SquareType.CHANCE
        else:
            self.type: SquareType = SquareType.PROPERTY

        # property info only
        self.color = color
        self._price = price
        self.house_cost = house_cost  # 蓋每棟房屋的金額
        self.tolls: list = tolls  # 過路費（空屋~5棟房屋）

        # property info only, change when gaming
        self.owner: Player = None
        self.level = 0  # 地產等級
        self.mortgaged = False  # 是否抵押中

    @property
    def price(self):
        if self.mortgaged:
            return self._price // 2
        if self.level > 0:
            return self.house_cost * self.level + self._price
        return self._price
    
    @price.setter
    def price(self, value):
        self._price = value

    def get_rent(self) -> int:
        # 過路費 要加上不同顏色的地產
        # 目前只考慮單一地產
        return self.tolls[self.level]
    
    def reset(self):
        # reset property info
        self.owner = None
        self.level = 0
        self.mortgaged = False

    
class Player:
    def __init__(self, name: str, user_id: int):
        self.name = name
        self.user_id = user_id
        self.money = START_MONEY  # 起始金額 如果小於0則破產   
        self.position = 0  # 目前位置
        self.jail_turns = 0
        self.properties: Dict[str, Square] = {}
        self.mortgage_properties: Dict[str, Square] = {}

    def move(self, steps: int, board_size: int) -> int:
        self.position = (self.position + steps) % board_size
        return self.position

    def pay(self, amount: int) -> bool:
        if self.money >= amount:
            self.money -= amount
            return True
        return False

    def receive(self, amount: int):
        self.money += amount
