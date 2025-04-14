import logging
import random
from typing import List, Optional
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config import TELEGRAM_TOKEN

# 設定日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 定義格子類型
class Square:
    def __init__(self, name: str, square_type: str, position: int, price: int = 0, rent: int = 0):
        self.name = name
        self.type = square_type  # 'property', 'chance', 'fate', 'jail', 'start'
        self.position = position
        self.price = price
        self.rent = rent
        self.owner = None

# 玩家類別
class Player:
    def __init__(self, name: str, user_id: int):
        self.name = name
        self.user_id = user_id
        self.money = 1500  # 起始金額
        self.position = 0  # 起始位置
        self.in_jail = False
        self.jail_turns = 0
        self.properties: List[Square] = []
        self.bankrupt = False

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

# 遊戲狀態
class GameState:
    def __init__(self):
        self.players: List[Player] = []
        self.started = False
        self.current_player_index = 0
        self.board: List[Square] = self._initialize_board()

    def _initialize_board(self) -> List[Square]:
        board = []
        # 建立遊戲板
        board.append(Square("起點", "start", 0))
        board.append(Square("台北", "property", 1, 600, 60))
        board.append(Square("機會", "chance", 2))
        board.append(Square("台中", "property", 3, 400, 40))
        board.append(Square("高雄", "property", 4, 500, 50))
        board.append(Square("命運", "fate", 5))
        board.append(Square("監獄", "jail", 6))
        board.append(Square("花蓮", "property", 7, 300, 30))
        return board

    def add_player(self, name: str, user_id: int) -> bool:
        if not self.started and len(self.players) < 6:
            player = Player(name, user_id)
            self.players.append(player)
            return True
        return False

    def get_current_player(self) -> Optional[Player]:
        if not self.players:
            return None
        return self.players[self.current_player_index]

    def next_turn(self):
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        while self.players[self.current_player_index].bankrupt:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)

    def get_square(self, position: int) -> Square:
        return self.board[position]

    def check_winner(self) -> Optional[Player]:
        active_players = [p for p in self.players if not p.bankrupt]
        if len(active_players) == 1:
            return active_players[0]
        return None

# 初始化遊戲狀態
game_state = GameState()

# 指令處理函數
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_name = update.effective_user.first_name
    user_id = update.effective_user.id
    if game_state.started:
        await update.message.reply_text("遊戲已經開始，無法加入！")
    else:
        if game_state.add_player(player_name, user_id):
            await update.message.reply_text(f"{player_name} 已加入遊戲！")
        else:
            await update.message.reply_text("玩家已滿，無法加入！")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if game_state.started:
        await update.message.reply_text("遊戲已經開始！")
    else:
        game_state.started = True
        await update.message.reply_text("遊戲開始！所有玩家準備好！")

async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_state.started:
        await update.message.reply_text("遊戲尚未開始！")
        return

    current_player = game_state.get_current_player()
    if not current_player or current_player.user_id != update.effective_user.id:
        await update.message.reply_text("現在不是你的回合！")
        return

    if current_player.in_jail:
        await update.message.reply_text(f"{current_player.name} 在監獄中！使用 /pay 支付 50 元離開，或等待 {3 - current_player.jail_turns} 回合。")
        current_player.jail_turns += 1
        if current_player.jail_turns >= 3:
            current_player.in_jail = False
            current_player.jail_turns = 0
        else:
            game_state.next_turn()
        return

    steps = random.randint(1, 6)
    old_position = current_player.position
    new_position = current_player.move(steps, len(game_state.board))
    
    # 經過起點獲得獎勵
    if new_position < old_position:
        current_player.receive(200)
        await update.message.reply_text(f"{current_player.name} 經過起點，獲得 200 元！")

    current_square = game_state.get_square(new_position)
    await update.message.reply_text(
        f"{current_player.name} 擲出了 {steps} 點，"
        f"移動到了 {current_square.name}！"
    )

    # 處理不同類型的格子
    if current_square.type == "property":
        if current_square.owner is None:
            await update.message.reply_text(
                f"這是一塊空地！價格：{current_square.price} 元\n"
                f"使用 /buy 購買此地產"
            )
        elif current_square.owner != current_player:
            rent = current_square.rent
            if current_player.pay(rent):
                current_square.owner.receive(rent)
                await update.message.reply_text(
                    f"{current_player.name} 支付 {rent} 元租金給 "
                    f"{current_square.owner.name}"
                )
            else:
                await update.message.reply_text(f"{current_player.name} 破產了！")
                current_player.bankrupt = True
    
    elif current_square.type == "chance" or current_square.type == "fate":
        effects = [
            ("獲得獎金", 100),
            ("繳納稅款", -50),
            ("中樂透", 200),
            ("醫療費", -100)
        ]
        effect, amount = random.choice(effects)
        if amount > 0:
            current_player.receive(amount)
        else:
            current_player.pay(-amount)
        await update.message.reply_text(f"{current_player.name} {effect}：{abs(amount)} 元")
    
    elif current_square.type == "jail":
        current_player.in_jail = True
        current_player.jail_turns = 0
        await update.message.reply_text(f"{current_player.name} 進入監獄！")

    # 檢查是否有玩家獲勝
    winner = game_state.check_winner()
    if winner:
        await update.message.reply_text(f"遊戲結束！{winner.name} 獲勝！")
        game_state = GameState()
    else:
        game_state.next_turn()
        next_player = game_state.get_current_player()
        await update.message.reply_text(f"輪到 {next_player.name} 的回合！")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_state.started:
        await update.message.reply_text("遊戲尚未開始！")
        return

    current_player = game_state.get_current_player()
    if not current_player or current_player.user_id != update.effective_user.id:
        await update.message.reply_text("現在不是你的回合！")
        return

    current_square = game_state.get_square(current_player.position)
    if current_square.type != "property":
        await update.message.reply_text("這個位置不能購買！")
        return

    if current_square.owner is not None:
        await update.message.reply_text("這塊地已經有主人了！")
        return

    if current_player.money < current_square.price:
        await update.message.reply_text("你的錢不夠！")
        return

    current_player.pay(current_square.price)
    current_square.owner = current_player
    current_player.properties.append(current_square)
    await update.message.reply_text(
        f"{current_player.name} 購買了 {current_square.name}，"
        f"支付 {current_square.price} 元！"
    )

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_state.started:
        await update.message.reply_text("遊戲尚未開始！")
        return

    current_player = game_state.get_current_player()
    if not current_player or current_player.user_id != update.effective_user.id:
        await update.message.reply_text("現在不是你的回合！")
        return

    if not current_player.in_jail:
        await update.message.reply_text("你不在監獄中！")
        return

    if current_player.pay(50):
        current_player.in_jail = False
        current_player.jail_turns = 0
        await update.message.reply_text(f"{current_player.name} 支付了 50 元離開監獄！")
    else:
        await update.message.reply_text("你的錢不夠支付罰金！")

async def richlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_state.started:
        await update.message.reply_text("遊戲尚未開始！")
        return

    result = "玩家財富排行：\n"
    for player in game_state.players:
        if player.bankrupt:
            status = "（已破產）"
        else:
            status = ""
            
        properties = ", ".join([p.name for p in player.properties]) or "無"
        result += f"\n{player.name}{status}:\n"
        result += f"- 現金: {player.money} 元\n"
        result += f"- 擁有地產: {properties}\n"
    
    await update.message.reply_text(result)

# 主函數
if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 註冊指令
    application.add_handler(CommandHandler("join", join))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("roll", roll))
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(CommandHandler("pay", pay))
    application.add_handler(CommandHandler("richlist", richlist))

    # 啟動 Bot
    application.run_polling()