"""
CSV Loader - ماژول بارگذاری و جستجو در CSV
Module for loading and searching in CSV files
"""

import pandas as pd
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Tuple, List


class CSVLoader:
    """
    بارگذاری و جستجو در فایل CSV
    Loads and searches CSV files
    """

    def __init__(self, csv_file: Path, question_col: str, answer_col: str, similarity_threshold: float = 0.6):
        """
        Initialize CSV Loader

        Args:
            csv_file: Path to CSV file
            question_col: Name of question column
            answer_col: Name of answer column
            similarity_threshold: Threshold for fuzzy matching (0.0-1.0)
        """
        self.csv_file = csv_file
        self.question_col = question_col
        self.answer_col = answer_col
        self.similarity_threshold = similarity_threshold
        self.data = None
        self.questions = []
        self._load_csv()

    def _load_csv(self) -> None:
        """لود کردن فایل CSV"""
        try:
            if not self.csv_file.exists():
                print(f"⚠️ فایل CSV پیدا نشد: {self.csv_file}")
                self.data = pd.DataFrame()
                return

            self.data = pd.read_csv(self.csv_file, encoding='utf-8')

            if self.question_col not in self.data.columns or self.answer_col not in self.data.columns:
                print("⚠️ ستون های مورد نظر در CSV پیدا نشد")
                self.data = pd.DataFrame()
                return

            self.questions = self.data[self.question_col].tolist()
            print(f"✅ {len(self.questions)} سوال بارگذاری شد")

        except Exception as e:
            print(f"❌ خطا در بارگذاری CSV: {e}")
            self.data = pd.DataFrame()

    def search(self, question: str) -> Optional[Tuple[str, float]]:
        """
        جستجو دقیق یا فازی در سوالات
        Search for question with fuzzy matching
        """
        if self.data.empty or not self.questions:
            return None

        question = question.strip()

        best_match = None
        best_score = 0

        for idx, saved_question in enumerate(self.questions):
            similarity = self._calculate_similarity(question.lower(), saved_question.lower())

            if similarity > best_score:
                best_score = similarity
                best_match = idx

        if best_score >= self.similarity_threshold:
            answer = self.data[self.answer_col].iloc[best_match]
            return answer, best_score

        return None

    @staticmethod
    def _calculate_similarity(text1: str, text2: str) -> float:
        """
        محاسبه شباهت بین دو متن
        Calculate similarity between two texts
        """
        return SequenceMatcher(None, text1, text2).ratio()

    def reload_csv(self) -> None:
        """دوباره بارگذاری فایل CSV"""
        self._load_csv()

    def get_all_qa(self) -> List[Tuple[str, str]]:
        """
        تمام سوالات و جوابات را برمی گرداند
        Returns all Q&A pairs
        """
        if self.data.empty:
            return []

        return list(zip(
            self.data[self.question_col].tolist(),
            self.data[self.answer_col].tolist()
        ))

    def add_qa(self, question: str, answer: str) -> bool:
        """
        یک سوال و جواب جدید اضافه می کند
        Add new Q&A pair
        """
        try:
            new_row = pd.DataFrame({
                self.question_col: [question],
                self.answer_col: [answer]
            })

            self.data = pd.concat([self.data, new_row], ignore_index=True)
            self.questions.append(question)

            self.data.to_csv(self.csv_file, index=False, encoding='utf-8')
            print("✅ سوال جدید اضافه شد")
            return True

        except Exception as e:
            print(f"❌ خطا در اضافه کردن سوال: {e}")
            return False

    def remove_qa(self, question: str) -> bool:
        """
        حذف یک سوال و جواب با متن دقیق سوال
        Remove a Q&A pair by exact question text
        """
        try:
            if self.data.empty:
                return False

            normalized = question.strip()
            mask = self.data[self.question_col].astype(str).str.strip() == normalized
            if not mask.any():
                return False

            self.data = self.data.loc[~mask].reset_index(drop=True)
            self.questions = self.data[self.question_col].tolist()
            self.data.to_csv(self.csv_file, index=False, encoding='utf-8')
            print("✅ سوال حذف شد")
            return True

        except Exception as e:
            print(f"❌ خطا در حذف سوال: {e}")
            return False
