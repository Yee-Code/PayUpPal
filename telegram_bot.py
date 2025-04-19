from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config import *
from game_state import *
from game_state_repository import *

repository = FirebaseGameStateRepository(FIREBASE_CRED_PATH)
# repository = LocalGameStateRepository()

# 關閉 httpx 的日誌
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# 多群組遊戲狀態與同步鎖
chat_games = {}  # chat_id: GameState
chat_locks = {}  # chat_id: asyncio.Lock

# 獲取遊戲狀態，優先從 Firebase 載入
def get_game_state(update: Update) -> GameState:
    # 群組的 ID
    chat_id = update.effective_chat.id
    if chat_id not in chat_games:
        # 嘗試從 Firebase 載入
        data = repository.load_game_state(str(chat_id))
        if data:
            chat_games[chat_id] = GameState.from_dict(data, update.message.reply_text)
        else:
            chat_games[chat_id] = GameState(update.message.reply_text)
    chat_games[chat_id].message_handler = update.message.reply_text
    return chat_games[chat_id]

# 使用鎖來確保同一時間只有一個使用者在操作遊戲狀態
async def with_lock(update: Update, context: ContextTypes.DEFAULT_TYPE, handler):
    chat_id = update.effective_chat.id
    if chat_id not in chat_locks:
        chat_locks[chat_id] = asyncio.Lock()
    lock = chat_locks[chat_id]
    async with lock:
        await handler(update, context)

# 在每次遊戲狀態變動後自動儲存
async def save_and_call(chat_id, func, *args, **kwargs):
    result = await func(*args, **kwargs)
    repository.save_game_state(str(chat_id), chat_games[chat_id].to_dict())
    return result

# 處理使用者輸入的訊息
async def handle_message_property(update: Update, context: ContextTypes.DEFAULT_TYPE, game_state: GameState) -> Square:
    # 假設訊息格式為 /command <property_name>
    message = update.message.text
    bot = await context.bot.get_me()
    message = message.replace(f"@{bot.username}", "").strip()
    logging.info(f"{update.effective_user.first_name}, {update.effective_user.id}, {message}")

    message_split = message.split(" ", 1)
    if len(message_split) < 2 or not message_split[1].strip():
        await update.message.reply_text(f"請在指令後面輸入地名。例如: {message_split[0]} 台北")
        return None
    
    square = game_state.get_square_by_name(message_split[1].strip())
    if not square:
        await game_state.message_handler("找不到該地產！")
    return square

# 指令處理函數
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    player_name = update.effective_user.first_name
    user_id = update.effective_user.id
    await save_and_call(update.effective_chat.id, game_state.add_player, player_name, user_id)
            
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    await save_and_call(update.effective_chat.id, game_state.start_game)

async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    user_id = update.effective_user.id
    await save_and_call(update.effective_chat.id, game_state.roll_dice, game_state.get_player(user_id))

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    user_id = update.effective_user.id
    player = game_state.get_player(user_id)
    if player:
        current_square = game_state.get_square(player.position)
        await save_and_call(update.effective_chat.id, game_state.buy_property, player, current_square)

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    user_id = update.effective_user.id
    player = game_state.get_player(user_id)
    square = await handle_message_property(update, context, game_state)
    if square:
        await save_and_call(update.effective_chat.id, game_state.sell_property, player, square)

async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    user_id = update.effective_user.id
    player = game_state.get_player(user_id)
    if player:
        current_square = game_state.get_square(player.position)
        await save_and_call(update.effective_chat.id, game_state.upgrade_property, player, current_square)

async def downgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    user_id = update.effective_user.id
    player = game_state.get_player(user_id)
    square = await handle_message_property(update, context, game_state)
    if square:
        await save_and_call(update.effective_chat.id, game_state.downgrade_property, player, square)

async def mortgage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    user_id = update.effective_user.id
    player = game_state.get_player(user_id)
    square = await handle_message_property(update, context, game_state)
    if square:
        await save_and_call(update.effective_chat.id, game_state.mortgage_property, player, square)

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    user_id = update.effective_user.id
    player = game_state.get_player(user_id)
    await save_and_call(update.effective_chat.id, game_state.pay, player)

async def nextplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    user_id = update.effective_user.id
    player = game_state.get_player(user_id)
    await save_and_call(update.effective_chat.id, game_state.next_turn, player)

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    user_id = update.effective_user.id
    player = game_state.get_player(user_id)
    await game_state.info(player)

async def richlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    await game_state.show_players()

async def board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    await game_state.show_board()

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_state = get_game_state(update)
    if not game_state.double_confirm:
        await update.message.reply_text("請再次輸入 /reset 來確認重置遊戲。")
        game_state.double_confirm = True
        return
    await save_and_call(update.effective_chat.id, game_state.reset_game)
    repository.delete_game_state(str(update.effective_chat.id))
    await update.message.reply_text("使用 /join 來加入遊戲。")


if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 註冊指令
    application.add_handler(CommandHandler("join", lambda u, c: with_lock(u, c, join)))
    application.add_handler(CommandHandler("start", lambda u, c: with_lock(u, c, start)))
    application.add_handler(CommandHandler("roll", lambda u, c: with_lock(u, c, roll)))
    application.add_handler(CommandHandler("buy", lambda u, c: with_lock(u, c, buy)))
    application.add_handler(CommandHandler("sell", lambda u, c: with_lock(u, c, sell)))
    application.add_handler(CommandHandler("upgrade", lambda u, c: with_lock(u, c, upgrade)))
    application.add_handler(CommandHandler("downgrade", lambda u, c: with_lock(u, c, downgrade)))
    application.add_handler(CommandHandler("mortgage", lambda u, c: with_lock(u, c, mortgage)))
    application.add_handler(CommandHandler("pay", lambda u, c: with_lock(u, c, pay)))
    application.add_handler(CommandHandler("next", lambda u, c: with_lock(u, c, nextplayer)))
    application.add_handler(CommandHandler("info", lambda u, c: with_lock(u, c, info)))
    application.add_handler(CommandHandler("richlist", lambda u, c: with_lock(u, c, richlist)))
    application.add_handler(CommandHandler("board", lambda u, c: with_lock(u, c, board)))
    application.add_handler(CommandHandler("reset", lambda u, c: with_lock(u, c, reset)))

    # 啟動 Bot
    application.run_polling()