from abc import ABC, abstractmethod

import firebase_admin
from firebase_admin import credentials, firestore


class GameStateRepository(ABC):
    @abstractmethod
    def save_game_state(self, chat_id: str, state: dict):
        """儲存指定 chat_id 的遊戲狀態 (dict 結構)"""
        pass

    @abstractmethod
    def load_game_state(self, chat_id: str) -> dict | None:
        """讀取指定 chat_id 的遊戲狀態，無資料則回傳 None"""
        pass

    @abstractmethod
    def delete_game_state(self, chat_id: str):
        """刪除指定 chat_id 的遊戲狀態"""
        pass


class FirebaseGameStateRepository(GameStateRepository):
    def __init__(self, cred_path: str, collection_name: str = "PayUpPal"):
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()
        self.collection = self.db.collection(collection_name)

    def save_game_state(self, chat_id: str, state: dict):
        self.collection.document(str(chat_id)).set(state)

    def load_game_state(self, chat_id: str) -> dict | None:
        doc = self.collection.document(str(chat_id)).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def delete_game_state(self, chat_id: str):
        self.collection.document(str(chat_id)).delete()


class LocalGameStateRepository(GameStateRepository):
    # def __init__(self, file_path: str):
    #     self.file_path = file_path

    def save_game_state(self, chat_id: str, state: dict):
        with open(chat_id + '.json', "w") as f:
            f.write(str(state))

    def load_game_state(self, chat_id: str) -> dict | None:
        try:
            with open(chat_id + '.json', "r") as f:
                return eval(f.read())
        except FileNotFoundError:
            return None

    def delete_game_state(self, chat_id: str):
        import os
        if os.path.exists(chat_id + '.json'):
            os.remove(chat_id + '.json')