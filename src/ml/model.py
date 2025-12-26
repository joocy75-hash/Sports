import logging
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder
import pickle
import os

logger = logging.getLogger(__name__)


class MatchPredictorML:
    def __init__(self, model_path="src/ml/model.pkl"):
        self.model = None
        self.model_path = model_path
        self.le_teams = LabelEncoder()
        self.le_leagues = LabelEncoder()

    def train(self, df: pd.DataFrame):
        """
        Train a LightGBM model on the historical data.
        """
        if df.empty:
            logger.warning("No data to train on.")
            return

        # Prepare Features (X) and Target (y)
        # We need to encode categorical variables
        df["LeagueID"] = self.le_leagues.fit_transform(df["LeagueName"])

        # Features: Rolling Stats (Performance Based)
        # NO ODDS included here.
        features = [
            "HomeAvgGF",
            "HomeAvgGA",
            "HomeAvgSF",
            "HomeAvgSA",
            "AwayAvgGF",
            "AwayAvgGA",
            "AwayAvgSF",
            "AwayAvgSA",
            "LeagueID",
        ]

        # Check if features exist
        missing_features = [f for f in features if f not in df.columns]
        if missing_features:
            logger.error(f"Missing features for training: {missing_features}")
            return

        X = df[features]
        y = df["FTR"].map(
            {"H": 0, "D": 1, "A": 2}
        )  # LightGBM expects integers for multiclass

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Train
        logger.info("Training LightGBM model (Performance Based)...")
        train_data = lgb.Dataset(X_train, label=y_train)
        valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

        params = {
            "objective": "multiclass",
            "num_class": 3,
            "metric": "multi_logloss",
            "verbosity": -1,
            "boosting_type": "gbdt",
        }

        self.model = lgb.train(
            params,
            train_data,
            valid_sets=[valid_data],
            num_boost_round=100,
            callbacks=[lgb.early_stopping(stopping_rounds=10)],
        )

        # Evaluate
        preds = self.model.predict(X_test)
        pred_labels = [p.argmax() for p in preds]
        acc = accuracy_score(y_test, pred_labels)
        logger.info(f"Model Accuracy: {acc:.4f}")
        logger.info("\n" + classification_report(y_test, pred_labels))

        # Save
        self.save_model()

    def save_model(self):
        if self.model:
            with open(self.model_path, "wb") as f:
                pickle.dump({"model": self.model, "le_leagues": self.le_leagues}, f)
            logger.info(f"Model saved to {self.model_path}")

    def load_model(self):
        if os.path.exists(self.model_path):
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
                self.model = data["model"]
                self.le_leagues = data["le_leagues"]
            logger.info("Model loaded.")
        else:
            logger.warning("Model file not found.")

    def predict_proba(self, home_stats: dict, away_stats: dict, league_name: str):
        """
        Predict probabilities based on team stats.
        stats dict should contain: avg_gf, avg_ga, avg_sf, avg_sa
        """
        if not self.model:
            self.load_model()

        if not self.model:
            return None

        try:
            league_id = self.le_leagues.transform([league_name])[0]
        except:
            league_id = 0  # Fallback

        # Map input dict keys to feature columns
        # Features: "HomeAvgGF", "HomeAvgGA", "HomeAvgSF", "HomeAvgSA", ...

        # Default values if missing
        def get_val(d, k):
            return d.get(k, 0.0)

        X = pd.DataFrame(
            [
                [
                    get_val(home_stats, "avg_gf"),
                    get_val(home_stats, "avg_ga"),
                    get_val(home_stats, "avg_sf"),
                    get_val(home_stats, "avg_sa"),
                    get_val(away_stats, "avg_gf"),
                    get_val(away_stats, "avg_ga"),
                    get_val(away_stats, "avg_sf"),
                    get_val(away_stats, "avg_sa"),
                    league_id,
                ]
            ],
            columns=[
                "HomeAvgGF",
                "HomeAvgGA",
                "HomeAvgSF",
                "HomeAvgSA",
                "AwayAvgGF",
                "AwayAvgGA",
                "AwayAvgSF",
                "AwayAvgSA",
                "LeagueID",
            ],
        )

        pred = self.model.predict(X)[0]
        return {"home": pred[0], "draw": pred[1], "away": pred[2]}
