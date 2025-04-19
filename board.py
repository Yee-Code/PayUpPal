from typing import List
from base import Square

# 棋盤
def initialize_board() -> List[Square]:
    board = [
        Square("起點"),
        Square("台北", color="紅色", price=600, tolls=[220, 1500, 3000, 6000, 12000], house_cost=2000),
        # Square("機會"),
        # Square("命運"),
        Square("監獄"),
        Square("台南", color="綠色", price=600, tolls=[220, 1500, 3000, 6000, 12000], house_cost=2000),
        Square("高雄", color="藍色", price=600, tolls=[220, 1500, 3000, 6000, 12000], house_cost=2000),
        # Square("機會"),
        Square("花蓮", color="黃色", price=600, tolls=[220, 1500, 3000, 6000, 12000], house_cost=2000),
        Square("台東", color="紫色", price=600, tolls=[220, 1500, 3000, 6000, 12000], house_cost=2000),
        # Square("命運"),
        Square("澎湖", color="橘色", price=600, tolls=[220, 1500, 3000, 6000, 12000], house_cost=2000),
        Square("基隆", color="紅色", price=600, tolls=[220, 1500, 3000, 6000, 12000], house_cost=2000),
        Square("監獄"),

    ]

    # 照加入順序設定每個方格的 position
    for i in range(len(board)):
        board[i].position = i

    return board
