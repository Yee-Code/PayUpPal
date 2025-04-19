import asyncio
import random
import logging
from typing import List, Optional

from base import *
from board import initialize_board
from chance import *


# 設定日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 遊戲狀態
class GameState:
    def __init__(self, message_handler):
        self.players: List[Player] = []
        self.player_dict: Dict[int, Player] = {}
        self.started = False
        self.current_player_index = 0
        self.board: List[Square] = initialize_board()
        self.board_dict: Dict[str, Square] = {square.name: square for square in self.board}
        self.message_handler = message_handler  # 訊息處理器
        self.ledger = {}  # 紀錄玩家的交易紀錄
        self.rolled = False  # 是否已經擲骰子
        self.double_confirm = False  # 確認是否reeset用

    def get_current_player(self) -> Optional[Player]:
        if not self.players:
            return None
        return self.players[self.current_player_index]
    
    def get_player(self, user_id: int) -> Optional[Player]:
        return self.player_dict.get(user_id)

    def get_square(self, position: int) -> Square:
        return self.board[position]
    
    def get_square_by_name(self, name: str) -> Optional[Square]:
        return self.board_dict.get(name)

    def check_winner(self) -> Optional[Player]:
        active_players = [p for p in self.players if p.money >= 0]
        if len(active_players) == 1:
            return active_players[0]
        return None

    async def add_player(self, name: str, user_id: int) -> bool:
        logging.info(f"玩家 {name} ，ID: {user_id}")

        if self.started:
            await self.message_handler("遊戲已經開始，無法加入。")
            return

        # 檢查玩家是否已經加入
        if self.get_player(user_id):
            await self.message_handler(f"{name} 已經加入遊戲！")
            return
        
        # 檢查玩家人數
        if len(self.players) < 6:
            player = Player(name, user_id)
            self.players.append(player)
            self.player_dict[user_id] = player

            await self.message_handler(f"{name} 加入遊戲！")
        else:
            await self.message_handler("玩家人數已滿，無法加入。")
        
    async def start_game(self):
        if self.started:
            await self.message_handler("遊戲已經開始。")
            return
        
        if len(self.players) < 2:
            await self.message_handler("至少需要兩名玩家才能開始遊戲。")
            return

        self.started = True
        await self.message_handler("遊戲開始！")

        # 隨機洗牌玩家順序
        random.shuffle(self.players)
        logging.info("遊戲開始~")
        await self.message_handler('玩家順序\n' + '\n'.join([f"{i+1}. {player.name}" for i, player in enumerate(self.players)]))

    async def roll_dice(self, player: Player):
        # 檢查遊戲是否開始
        if not self.started:
            await self.message_handler("遊戲尚未開始。")
            return

        # 檢查當前回合玩家
        current_player = self.get_current_player()
        if not current_player or current_player.user_id != player.user_id:
            await self.message_handler("現在不是你的回合！")
            return
        
        # 檢查玩家是否在監獄中
        if current_player.jail_turns > 0:
            current_player.jail_turns -= 1
            self.rolled = True
            await self.message_handler(f"{player.name}在監獄中，無法擲骰子。\n還需{current_player.jail_turns}回合才能出獄。")
            await self.next_turn(player)
            return
        
        # 檢查是否已經擲骰子
        if self.rolled:
            await self.message_handler(f"{player.name} 已經擲過骰子了！")
            return

        # 擲骰子
        self.rolled = True
        dice_roll = random.randint(1, 6) + random.randint(1, 6)
        await self.message_handler(f"{player.name} 擲出了 {dice_roll} 點！")
        old_position = current_player.position
        new_position = current_player.move(dice_roll, len(self.board))

        current_square = self.get_square(new_position)
        await self.message_handler(f"移動到了 {current_square.name}！")

        # 經過起點獲得獎勵
        if new_position != 0 and new_position < old_position:
            current_player.receive(PASS_GO_MONEY)
            await self.message_handler(f"{current_player.name} 經過起點，獲得 {PASS_GO_MONEY} 元！")

        # 處理不同類型的格子
        if current_square.type == SquareType.JAIL:
            current_player.jail_turns = JAIL_TIME
            await self.message_handler(f"{current_player.name} 被送進監獄！")
            await self.next_turn(player)
            return
        if current_square.type == SquareType.START:
            await self.next_turn(player)
            return
        
        if current_square.type == SquareType.CHANCE:
            chance_card = get_chance_card()
            await self.message_handler(chance_card.card)
            await self.message_handler("尚未實作")
            # if chance_card.lost > 0:
            #     current_player.pay(chance_card.lost)
            #     await self.message_handler(f"{current_player.name} 繳交了 {chance_card.lost} 元罰款！")
            # if chance_card.gain > 0:
            #     current_player.receive(chance_card.gain)
            #     await self.message_handler(f"{current_player.name} 獲得了 {chance_card.gain} 元獎金！")
            return
        
        if current_square.type == SquareType.PROPERTY:
            if current_square.owner == None:
                await self.message_handler(f"這是一塊空地！價格: {current_square.price} 元")
                await self.message_handler(f"使用 /buy 購買此地產")
            elif current_square.owner == current_player:
                await self.message_handler(f"{current_player.name} 擁有這塊地產！")
                await self.message_handler(f"使用 /upgrade 升級此地產。升級價格: {current_square.house_cost} 元")
            else:
                await self.message_handler(f"{current_player.name} 需要支付 {current_square.get_rent()} 元租金給 {current_square.owner.name}！")
                if current_player.pay(current_square.get_rent()):
                    await self.message_handler(f"{current_player.name} 支付了租金！")
                    await self.next_turn(player)
                else:
                    self.ledger = {'from': current_player, 'amount': current_square.get_rent(), 'to': current_square.owner}
                    await self.message_handler(f"{current_player.name} 無法支付租金！")
                    await self.message_handler(f"使用 /mortgage 抵押地產")
                    await self.message_handler(f"使用 /downgrade 降級地產")
                    await self.message_handler(f"使用 /sell 出售地產")
        else:
            logging.error(f"未知的地產擁有者: {current_square.owner.name}，玩家: {current_player.name}")

    async def buy_property(self, player: Player, estate: Square):
        # 檢查遊戲是否開始
        if not self.started:
            await self.message_handler("遊戲尚未開始。")
            return
        
        # 檢查是否已經擲骰子
        if not self.rolled:
            await self.message_handler("請先擲骰子！")
            return

        # 檢查當前回合玩家
        current_player = self.get_current_player()
        if not current_player or current_player.user_id != player.user_id:
            await self.message_handler("現在不是你的回合！")
            return
        
        # 檢查地產是否是使用者當前位置
        if current_player.position != estate.position:
            await self.message_handler(f"{estate.name} 不是你當前的位置！")
            return

        # 檢查地產是否存在
        if estate.type != SquareType.PROPERTY:
            await self.message_handler(f"{estate.name} 不是地產！")
            return
        
        # 檢查地產擁有者
        if estate.owner is not None:
            await self.message_handler(f"{estate.name} 已經被 {estate.owner.name} 擁有！")
            return
        
        # 檢查玩家金額是否足夠
        if player.money < estate.price:
            await self.message_handler(f"{player.name} 無法購買 {estate.name}！")
            await self.message_handler(f"使用 /mortgage 抵押地產")
            await self.message_handler(f"使用 /downgrade 降級地產")
            await self.message_handler(f"使用 /sell 出售地產")
            return
        
        if estate.mortgaged:
            del player.mortgage_properties[estate.name]
            estate.mortgaged = False
        player.pay(estate.price)
        estate.owner = player
        player.properties[estate.name] = estate
        await self.message_handler(f"{player.name} 購買了 {estate.name}！")
        await self.next_turn(player)

    async def sell_property(self, player: Player, estate: Square):
        # 檢查遊戲是否開始
        if not self.started:
            await self.message_handler("遊戲尚未開始。")
            return

        # 檢查當前回合玩家
        current_player = self.get_current_player()
        if not current_player or current_player.user_id != player.user_id:
            await self.message_handler("現在不是你的回合！")
            return
        
        # 檢查地產是否存在
        if estate.type != SquareType.PROPERTY:
            await self.message_handler(f"{estate.name} 不是地產！")
            return
        
        # 檢查地產擁有者
        if estate.owner != player:
            await self.message_handler(f"{estate.name} 不是你的地產！")
            return
        
        # 出售地產
        message = f"{player.name} 出售 {estate.name}{'（抵押中）' if estate.mortgaged else ' level: ' + str(estate.level)} {estate.price} 元！"
        player.receive(estate.price)
        estate.reset()
        del player.properties[estate.name]
        await self.message_handler(message)

    async def upgrade_property(self, player: Player, estate: Square):
        # 檢查遊戲是否開始
        if not self.started:
            await self.message_handler("遊戲尚未開始。")
            return
        
        # 檢查是否已經擲骰子
        if not self.rolled:
            await self.message_handler("請先擲骰子！")
            return

        # 檢查當前回合玩家
        current_player = self.get_current_player()
        if not current_player or current_player.user_id != player.user_id:
            await self.message_handler("現在不是你的回合！")
            return
        
        # 檢查地產是否是使用者當前位置
        if current_player.position != estate.position:
            await self.message_handler(f"{estate.name} 不是你當前的位置！")
            return
        
        # 檢查地產是否存在
        if estate.type != SquareType.PROPERTY:
            await self.message_handler(f"{estate.name} 不是地產！")
            return
        
        # 檢查地產擁有者
        if estate.owner != player:
            await self.message_handler(f"{estate.name} 不是你的地產！")
            return
        
        # 檢查地產是否抵押
        if estate.mortgaged:
            await self.message_handler(f"{estate.name} 已經抵押了，無法升級！")
            return
        
        # 檢查地產等級
        if estate.level >= 5:
            await self.message_handler(f"{estate.name} 已經是最高級了！")
            return
        
        # 檢查玩家金額是否足夠
        if player.money < estate.house_cost:
            await self.message_handler(f"{player.name} 沒有足夠的錢來升級 {estate.name}！")
            return

        # 升級地產
        player.pay(estate.house_cost)
        estate.level += 1
        await self.message_handler(f"{player.name} 升級了 {estate.name} 到 {estate.level} 級！")
        await self.next_turn(player)

    async def downgrade_property(self, player: Player, estate: Square):
        # 檢查遊戲是否開始
        if not self.started:
            await self.message_handler("遊戲尚未開始。")
            return

        # 檢查當前回合玩家
        current_player = self.get_current_player()
        if not current_player or current_player.user_id != player.user_id:
            await self.message_handler("現在不是你的回合！")
            return
        
        # 檢查地產是否存在
        if estate.type != SquareType.PROPERTY:
            await self.message_handler(f"{estate.name} 不是地產！")
            return
        
        # 檢查地產擁有者
        if estate.owner != player:
            await self.message_handler(f"{estate.name} 不是你的地產！")
            return
        
        # 檢查地產是否抵押
        if estate.mortgaged:
            await self.message_handler(f"{estate.name} 已經抵押了，無法降級！")
            return
        
        # 檢查地產等級
        if estate.level <= 0:
            await self.message_handler(f"{estate.name} 已經是最低級了！")
            return
        
        # 降級地產
        downgrade_cost = estate.house_cost
        player.receive(downgrade_cost)
        estate.level -= 1
        await self.message_handler(f"{player.name} 降級 {estate.name} 到 {estate.level} 級！")

    async def mortgage_property(self, player: Player, estate: Square):
        # 檢查遊戲是否開始
        if not self.started:
            await self.message_handler("遊戲尚未開始。")
            return

        # 檢查當前回合玩家
        current_player = self.get_current_player()
        if not current_player or current_player.user_id != player.user_id:
            await self.message_handler("現在不是你的回合！")
            return
        
        # 檢查地產是否存在
        if estate.type != SquareType.PROPERTY:
            await self.message_handler(f"{estate.name} 不是地產！")
            return
        
        # 檢查地產擁有者
        if estate.owner != player:
            await self.message_handler(f"{estate.name} 不是你的地產！")
            return
        
        # 抵押地產
        if estate.mortgaged:
            await self.message_handler(f"{estate.name} 已經抵押了，無法再次抵押！")
            return
        
        # 檢查地產等級
        if estate.level > 0:
            await self.message_handler(f"{estate.name} 已經升級了，無法抵押！")
            return

        estate.mortgaged = True
        player.receive(estate.price)
        player.mortgage_properties[estate.name] = estate
        del player.properties[estate.name]
        await self.message_handler(f"{player.name} 抵押了 {estate.name}！")

    async def pay(self, player: Player):
        # 檢查遊戲是否開始
        if not self.started:
            await self.message_handler("遊戲尚未開始。")
            return
        
        # 檢查當前回合玩家
        current_player = self.get_current_player()
        if current_player.user_id != player.user_id:
            await self.message_handler("現在不是你的回合！")
            return
        
        # 檢查是否有欠款
        if not self.ledger:
            await self.message_handler(f"{player.name} 沒有欠款！")
            return
        
        # 檢查玩家金額是否足夠
        if player.money < self.ledger['amount']:
            if player.properties or player.mortgage_properties:
                await self.message_handler(f"{player.name} 的金額不足！ 請變賣地產！")
                return
            else:
                # self.ledger['to'].receive(self.ledger['from'].money)
                self.ledger['from'].money = -1
                await self.message_handler(f"{player.name} 已破產！")
                await self.next_turn(player)
        else:
            # 支付欠款
            player.pay(self.ledger['amount'])
            self.ledger['to'].receive(self.ledger['amount'])
            await self.message_handler(f"{player.name} 支付了 {self.ledger['amount']} 元給 {self.ledger['to'].name}！")
        
        self.ledger.clear()

        # 下一回合
        winner = self.check_winner()
        if winner:
            await self.message_handler(f"{winner.name} 獲勝了！ 共有 {winner.money} 元！")
            await self.reset_game()

    async def next_turn(self, player: Player):
        # 檢查遊戲是否開始
        if not self.started:
            await self.message_handler("遊戲尚未開始。")
            return
        
        # 檢查當前回合玩家
        current_player = self.get_current_player()
        if current_player != player:
            await self.message_handler("現在不是你的回合！")
            return

        # 檢查是否已經擲骰子
        if not self.rolled:
            await self.message_handler("請先擲骰子！")
            return
        
        # 檢查是否欠賬
        if self.ledger:
            await self.message_handler(f"{current_player.name} 你有未結清的債務！")
            return

        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        await self.message_handler(f"輪到 {self.players[self.current_player_index].name} 了！")
        bankrupt_count = 0
        while self.players[self.current_player_index].money < 0:
            await self.message_handler(f"{self.players[self.current_player_index].name} 已破產！自動跳下一位玩家。")
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            bankrupt_count += 1
            if bankrupt_count >= len(self.players):  # Check if all players are bankrupt 不太可能發生
                await self.message_handler("所有玩家都已破產，遊戲結束！")
                await self.reset_game()
                return
            await self.message_handler(f"輪到 {self.players[self.current_player_index].name} 了！")

        self.rolled = False

    async def info(self, player: Player):
        # 顯示當前玩家資訊
        if not self.players:
            await self.message_handler("目前沒有玩家參加遊戲。")
            return
        
        message = [f"{player.name}:{player.user_id}，現金: {player.money} 元"]
        message.append(f"當前位置: {self.board[player.position].name}")
        if player.properties:
            message.append(f"地產: {'\n'.join([f'\t{p.name} level: {p.level}' for p in player.properties.values()])}")
        if player.mortgage_properties:
            message.append(f"抵押地產: {'\n'.join([p.name for p in player.mortgage_properties.values()])}")
        if self.ledger:
            message.append(f"欠{self.ledger['to'].name}{self.ledger['amount']} 元")
        await self.message_handler('\n'.join(message))

    async def show_players(self):
        # 顯示所有玩家資訊
        if not self.players:
            await self.message_handler("目前沒有玩家參加遊戲。")
            return
        
        players_info = ["目前玩家: "]
        for player in self.players:
            players_info.append(f"  {player.name}:{player.user_id}，現金: {player.money} 元")
        await self.message_handler('\n'.join(players_info))

    async def show_board(self):
        # 顯示遊戲板
        board_info = ["遊戲板: "]
        for i, square in enumerate(self.board):
            line = f"{i:2}: {square.name}"
            if square._price and square.owner is None:  
                line += f" ({square._price})"
            if square.owner:
                line += f" {square.owner.name} level: {square.level}"
            if square.mortgaged:
                line += " (抵押中)"
            board_info.append(line)
        await self.message_handler('\n'.join(board_info))

    async def reset_game(self):
        self.double_confirm = False
        self.players.clear()
        self.player_dict.clear()
        self.started = False
        self.current_player_index = 0
        self.ledger.clear()
        self.rolled = False
        for square in self.board:
            square.reset()
        await self.message_handler("遊戲已重置！")

    def to_dict(self):
        """將 GameState 轉為可序列化 dict"""
        return {
            'players': [self._player_to_dict(p) for p in self.players],
            'started': self.started,
            'current_player_index': self.current_player_index,
            'board': [self._square_to_dict(s) for s in self.board],
            'ledger': self._ledger_to_dict(self.ledger),
            'rolled': self.rolled,
            'double_confirm': self.double_confirm
        }

    @staticmethod
    def from_dict(data, message_handler):
        """從 dict 還原 GameState 物件"""
        obj = GameState(message_handler)
        obj.players = [obj._player_from_dict(p) for p in data['players']]
        obj.player_dict = {p.user_id: p for p in obj.players}
        obj.started = data['started']
        obj.current_player_index = data['current_player_index']
        obj.board = [obj._square_from_dict(s) for s in data['board']]
        obj.board_dict = {s.name: s for s in obj.board}
        obj.ledger = obj._ledger_from_dict(data['ledger'], obj.player_dict)
        obj.rolled = data['rolled']
        obj.double_confirm = data['double_confirm']

        # id 轉為 物件 
        for p in obj.players:
            p.properties = {name: obj.board_dict[name] for name in p.properties if name in obj.board_dict}
            p.mortgage_properties = {name: obj.board_dict[name] for name in p.mortgage_properties if name in obj.board_dict}
        for s in obj.board:
            if s.owner:
                s.owner = obj.player_dict[s.owner]
        if obj.ledger:
            obj.ledger['from'] = obj.player_dict[obj.ledger['from']]
            obj.ledger['to'] = obj.player_dict[obj.ledger['to']]
        return obj

    def _player_to_dict(self, player):
        # 使用 vars() 方式簡化 player 轉 dict
        d = vars(player).copy()
        d['properties'] = list(player.properties.keys())  # 轉為 id 之後再從 id 轉回物件字典
        d['mortgage_properties'] = list(player.mortgage_properties.keys())
        return d

    def _player_from_dict(self, data):
        p = Player(data['name'], data['user_id'])
        for k, v in data.items():
            setattr(p, k, v)
        # properties/mortgage_properties 會在 from_dict 裡處理成物件
        return p

    def _square_to_dict(self, square):
        d = vars(square).copy()
        d['type'] = square.type.name
        d['owner'] = square.owner.user_id if square.owner else None
        return d

    def _square_from_dict(self, data):
        s = Square(
            name=data['name'],
            color=data['color'],
            price=data['_price'],
            tolls=data['tolls'],
            house_cost=data['house_cost']
        )
        s.type = SquareType[data['type']]
        s.position = data['position']
        s.level = data['level']
        s.mortgaged = data['mortgaged']
        s.owner = data['owner']  # wait for player_dict
        return s

    def _ledger_to_dict(self, ledger):
        if not ledger:
            return {}
        return {
            'from': ledger['from'].user_id,
            'to': ledger['to'].user_id,
            'amount': ledger['amount']
        }

    def _ledger_from_dict(self, data, player_dict):
        if not data:
            return {}
        return {
            'from': player_dict[data['from']],  # wait for player_dict
            'to': player_dict[data['to']],      # wait for player_dict
            'amount': data['amount']
        }

async def async_print(msg):
        print(msg)


if __name__ == '__main__':
    game = GameState(async_print)
    asyncio.run(game.add_player("Alice", 1))
    print("------------------")
    asyncio.run(game.add_player("Bob", 2))
    print("------------------")
    asyncio.run(game.start_game())
    print("------------------")
    asyncio.run(game.show_players())
    print("------------------")

    asyncio.run(game.roll_dice(game.get_current_player()))
    print("------------------")
    asyncio.run(game.buy_property(game.get_current_player(), game.get_square(game.get_current_player().position)))
    asyncio.run(game.upgrade_property(game.get_current_player(), game.get_square(game.get_current_player().position)))
    asyncio.run(game.next_turn(game.get_current_player()))
    print("------------------")
    asyncio.run(game.show_players())
    print("------------------")
    asyncio.run(game.show_board())
    print("------------------")

    asyncio.run(game.roll_dice(game.get_current_player()))
    print("------------------")
    asyncio.run(game.sell_property(game.get_current_player(), game.get_square(game.get_current_player().position)))
    print("------------------")
    asyncio.run(game.show_players())
    print("------------------")
    asyncio.run(game.show_board())