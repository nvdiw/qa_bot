"""
CSV Loader - ماژول بارگذاری و جستجو در CSV
Module for loading and searching in CSV files
"""

import re
import unicodedata
import pandas as pd
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Tuple, List, Set, Dict


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
        self.normalized_questions: List[str] = []
        self.question_tokens: List[Set[str]] = []
        self.question_chargrams: List[Set[str]] = []
        self.known_tokens: Set[str] = set()
        self._load_csv()

    def _load_csv(self) -> None:
        """لود کردن فایل CSV"""
        try:
            if not self.csv_file.exists():
                print(f"⚠️ فایل CSV پیدا نشد: {self.csv_file}")
                self.data = pd.DataFrame()
                return

            self.data = pd.read_csv(self.csv_file, encoding='utf-8-sig')

            if self.question_col not in self.data.columns or self.answer_col not in self.data.columns:
                print("⚠️ ستون های مورد نظر در CSV پیدا نشد")
                self.data = pd.DataFrame()
                return

            self.questions = self.data[self.question_col].astype(str).fillna("").tolist()
            self._rebuild_search_cache()
            print(f"✅ {len(self.questions)} سوال بارگذاری شد")

        except Exception as e:
            print(f"❌ خطا در بارگذاری CSV: {e}")
            self.data = pd.DataFrame()

    def search(self, question: str) -> Optional[Tuple[str, float]]:
        """
        جستجو دقیق یا فازی در سوالات
        Search for question with fuzzy matching
        """
        results = self.search_many(question, max_answers=1)
        if not results:
            return None
        return results[0]

    def search_many(self, question: str, max_answers: int = 2) -> List[Tuple[str, float]]:
        """
        جستجو و برگرداندن چند پاسخ معتبر برای پیام کاربر
        Search and return up to max_answers matched answers.
        """
        if self.data.empty or not self.questions or max_answers <= 0:
            return []

        user_candidates = self._extract_question_candidates(question)
        if not user_candidates:
            return []

        matched_scores: Dict[int, float] = {}

        for candidate in user_candidates:
            if self._is_gibberish(candidate):
                continue

            candidate_norm = self._normalize_text(candidate)
            candidate_tokens = self._autocorrect_tokens(self._tokenize(candidate_norm))
            candidate_chargrams = self._char_ngrams(candidate_norm, 3)
            local_best_idx = None
            local_best_score = 0.0
            local_second_best = 0.0

            for idx, _ in enumerate(self.questions):
                similarity = self._calculate_similarity(
                    candidate_norm=candidate_norm,
                    candidate_tokens=candidate_tokens,
                    candidate_chargrams=candidate_chargrams,
                    question_norm=self.normalized_questions[idx],
                    question_tokens=self.question_tokens[idx],
                    question_chargrams=self.question_chargrams[idx],
                )

                if similarity > local_best_score:
                    local_second_best = local_best_score
                    local_best_score = similarity
                    local_best_idx = idx
                elif similarity > local_second_best:
                    local_second_best = similarity

            local_confident = (local_best_score - local_second_best) >= 0.03 or local_best_score >= 0.8
            if local_best_idx is None:
                continue
            best_token_overlap = self._fuzzy_token_overlap(candidate_tokens, self.question_tokens[local_best_idx])
            threshold = self.similarity_threshold
            if best_token_overlap >= 0.8:
                threshold = max(0.5, self.similarity_threshold - 0.08)
            elif candidate_tokens & self.question_tokens[local_best_idx] and best_token_overlap >= 0.5:
                threshold = max(0.5, self.similarity_threshold - 0.1)

            if local_best_score < threshold:
                continue
            if not (local_confident or local_best_score >= 0.88):
                continue

            prev = matched_scores.get(local_best_idx, 0.0)
            if local_best_score > prev:
                matched_scores[local_best_idx] = local_best_score

        ranked_matches = sorted(matched_scores.items(), key=lambda item: item[1], reverse=True)
        if not ranked_matches:
            return []

        results: List[Tuple[str, float]] = []
        seen_answers = set()
        for idx, score in ranked_matches:
            answer = str(self.data[self.answer_col].iloc[idx])
            answer_key = answer.strip()
            if not answer_key or answer_key in seen_answers:
                continue
            seen_answers.add(answer_key)
            results.append((answer, score))
            if len(results) >= max_answers:
                break

        return results

    @staticmethod
    def _calculate_similarity(
        candidate_norm: str,
        candidate_tokens: Set[str],
        candidate_chargrams: Set[str],
        question_norm: str,
        question_tokens: Set[str],
        question_chargrams: Set[str],
    ) -> float:
        """
        محاسبه شباهت بین دو متن
        Calculate similarity between two texts
        """
        if not candidate_norm or not question_norm:
            return 0.0
        if candidate_norm == question_norm:
            return 1.0

        seq_score = SequenceMatcher(None, candidate_norm, question_norm).ratio()
        token_score = CSVLoader._jaccard(candidate_tokens, question_tokens)
        chargram_score = CSVLoader._jaccard(candidate_chargrams, question_chargrams)
        fuzzy_token_overlap = CSVLoader._fuzzy_token_overlap(candidate_tokens, question_tokens)
        token_seq_score = 0.0
        if candidate_tokens and question_tokens:
            token_seq_score = SequenceMatcher(
                None,
                " ".join(sorted(candidate_tokens)),
                " ".join(sorted(question_tokens)),
            ).ratio()

        if candidate_tokens and question_tokens:
            overlap = len(candidate_tokens & question_tokens)
            contain_score = overlap / max(1, min(len(candidate_tokens), len(question_tokens)))
        else:
            contain_score = 0.0
        contain_score = max(contain_score, fuzzy_token_overlap)

        subset_bonus = 0.0
        if candidate_tokens and question_tokens and (
            candidate_tokens <= question_tokens or question_tokens <= candidate_tokens
        ):
            subset_bonus = 0.18 if min(len(candidate_tokens), len(question_tokens)) <= 2 else 0.08

        typo_bonus = 0.0
        if candidate_tokens and question_tokens and (candidate_tokens & question_tokens):
            typo_bonus = 0.07 if min(len(candidate_tokens), len(question_tokens)) <= 2 else 0.04

        score = (
            (0.25 * seq_score)
            + (0.3 * contain_score)
            + (0.2 * token_score)
            + (0.1 * chargram_score)
            + (0.15 * token_seq_score)
            + subset_bonus
            + typo_bonus
        )
        return min(score, 1.0)

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
            self._append_to_search_cache(question)

            self.data.to_csv(self.csv_file, index=False, encoding='utf-8-sig')
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
            self._rebuild_search_cache()
            self.data.to_csv(self.csv_file, index=False, encoding='utf-8-sig')
            print("✅ سوال حذف شد")
            return True

        except Exception as e:
            print(f"❌ خطا در حذف سوال: {e}")
            return False

    @staticmethod
    def _jaccard(a: Set[str], b: Set[str]) -> float:
        if not a or not b:
            return 0.0
        union = a | b
        if not union:
            return 0.0
        return len(a & b) / len(union)

    @staticmethod
    def _fuzzy_token_overlap(a: Set[str], b: Set[str], min_ratio: float = 0.72) -> float:
        if not a or not b:
            return 0.0

        left = list(a)
        right = list(b)
        smaller, larger = (left, right) if len(left) <= len(right) else (right, left)

        matched = 0
        for tok1 in smaller:
            best_ratio = 0.0
            for tok2 in larger:
                ratio = SequenceMatcher(None, tok1, tok2).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
            if best_ratio >= min_ratio:
                matched += 1

        return matched / max(1, len(smaller))

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = unicodedata.normalize("NFKC", str(text or ""))
        text = text.lower()
        text = text.replace("ي", "ی").replace("ك", "ک")
        text = text.replace("\u200c", " ")

        # Remove Arabic diacritics.
        text = re.sub(r"[\u0617-\u061A\u064B-\u0652]", "", text)
        text = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _tokenize(normalized_text: str) -> Set[str]:
        return {
            CSVLoader._normalize_token(tok) for tok in normalized_text.split()
            if len(tok) >= 2 and (tok == "سلام" or tok not in CSVLoader._STOPWORDS)
        }

    @staticmethod
    def _normalize_token(token: str) -> str:
        tok = token.strip()
        # Collapse accidental repeats for common Persian typo patterns.
        tok = re.sub(r"([یي])\1+", r"\1", tok)
        tok = re.sub(r"(.)\1{2,}", r"\1", tok)
        return tok

    def _autocorrect_tokens(self, tokens: Set[str]) -> Set[str]:
        if not tokens or not self.known_tokens:
            return tokens

        corrected: Set[str] = set()
        for tok in tokens:
            if tok in self.known_tokens or len(tok) < 3:
                corrected.add(tok)
                continue

            best = tok
            best_ratio = 0.0
            for known in self.known_tokens:
                if abs(len(known) - len(tok)) > 2:
                    continue
                ratio = SequenceMatcher(None, tok, known).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best = known

            if best_ratio >= 0.72:
                corrected.add(best)
            else:
                corrected.add(tok)
        return corrected

    @staticmethod
    def _char_ngrams(text: str, n: int = 3) -> Set[str]:
        compact = text.replace(" ", "")
        if len(compact) < n:
            return {compact} if compact else set()
        return {compact[i:i + n] for i in range(len(compact) - n + 1)}

    @staticmethod
    def _is_gibberish(text: str) -> bool:
        raw = (text or "").strip()
        if not raw:
            return True

        alnum = re.sub(r"[^0-9a-zA-Z\u0600-\u06FF]", "", raw)
        if len(alnum) < 3:
            return True

        if len(raw) >= 8:
            unique_ratio = len(set(raw)) / max(1, len(raw))
            if unique_ratio < 0.2:
                return True

        if re.search(r"(.)\1{3,}", raw):
            return True

        return False

    def _extract_question_candidates(self, user_text: str) -> List[str]:
        raw = (user_text or "").strip()
        if not raw:
            return []

        candidates = [raw]

        # If message starts with greeting and continues, add tail as a separate candidate.
        tail = re.sub(
            r"^\s*(سلام|درود|خوبی|خوبین|صبح بخیر|شب بخیر|وقت بخیر)\s+",
            "",
            raw,
            flags=re.IGNORECASE,
        ).strip()
        if tail and tail != raw and len(tail) >= 3:
            candidates.append(tail)

        # Split by common question separators to handle multi-question messages.
        for part in re.split(r"[?\n\r!؛;]+|[؟]+", raw):
            part = part.strip()
            if len(part) >= 3:
                candidates.append(part)

        # If text is very long, also split by connecting conjunction.
        if " و " in raw and len(raw) >= 25:
            for part in raw.split(" و "):
                part = part.strip()
                if len(part) >= 3:
                    candidates.append(part)

        unique: List[str] = []
        seen = set()
        for item in candidates:
            norm = re.sub(r"\s+", " ", item).strip()
            if not norm:
                continue
            key = norm.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(norm)
            if len(unique) >= 10:
                break
        return unique

    def _append_to_search_cache(self, question: str) -> None:
        norm = self._normalize_text(question)
        tokens = self._tokenize(norm)
        self.normalized_questions.append(norm)
        self.question_tokens.append(tokens)
        self.question_chargrams.append(self._char_ngrams(norm, 3))
        self.known_tokens.update(tokens)

    def _rebuild_search_cache(self) -> None:
        self.normalized_questions = []
        self.question_tokens = []
        self.question_chargrams = []
        self.known_tokens = set()
        for question in self.questions:
            self._append_to_search_cache(question)
    _STOPWORDS = {
        "لطفا", "خواهشا", "ممنون", "مرسی", "سلام", "درود",
        "میخواستم", "میخواهم", "میخوام", "میشه", "میشه؟", "میتونم", "میتونید",
        "اگر", "اگه", "امکان", "داره", "دارد", "است", "هست",
        "درباره", "مورد", "این", "اون", "آن", "را", "رو",
        "توضیح", "بده", "بدید", "کن", "کنید",
    }
