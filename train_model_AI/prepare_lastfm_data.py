from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from recommender import ContentBasedRecommender


BASE_DIR = Path(__file__).resolve().parent

def get_default_path(filename: str) -> Path:
    path_inside = BASE_DIR / "data" / filename
    if path_inside.exists():
        return path_inside
    return BASE_DIR.parent / "data" / filename


DEFAULT_SPOTIFY_PATH = get_default_path("dataset.csv")
DEFAULT_LASTFM_PATH = get_default_path("usersha1-artmbid-artname-plays.tsv")
DEFAULT_OUTPUT_PATH = get_default_path("lastfm_user_artist_interactions.csv")
DEFAULT_SUMMARY_PATH = get_default_path("lastfm_prepare_summary.json")

csv.field_size_limit(sys.maxsize)


def normalize_artist(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def build_spotify_artist_index(dataset_path: Path) -> dict[str, dict[str, object]]:
    recommender = ContentBasedRecommender(dataset_path)
    artist_index: dict[str, dict[str, object]] = {}

    for artists in recommender.df["artist"].dropna():
        for artist in str(artists).split(";"):
            artist = artist.strip()
            normalized_artist = normalize_artist(artist)
            if not normalized_artist:
                continue

            if normalized_artist not in artist_index:
                artist_index[normalized_artist] = {
                    "display_name": artist,
                    "track_count": 0,
                }
            artist_index[normalized_artist]["track_count"] = int(
                artist_index[normalized_artist]["track_count"]
            ) + 1

    return artist_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare real Last.fm implicit-feedback data for the music recommender.",
    )
    parser.add_argument("--spotify-path", type=Path, default=DEFAULT_SPOTIFY_PATH)
    parser.add_argument("--lastfm-path", type=Path, default=DEFAULT_LASTFM_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="Maximum Last.fm rows to read. Use 0 to read the full file.",
    )
    parser.add_argument(
        "--max-users",
        type=int,
        default=50000,
        help="Maximum eligible users to export. Use 0 for no user limit.",
    )
    parser.add_argument("--min-plays", type=int, default=5)
    parser.add_argument("--min-artists-per-user", type=int, default=5)
    parser.add_argument("--max-artists-per-user", type=int, default=50)
    return parser.parse_args()


def write_user_interactions(
    writer: csv.DictWriter,
    user_id: str,
    interactions: list[dict[str, object]],
    min_artists_per_user: int,
    max_artists_per_user: int,
) -> int:
    if len(interactions) < min_artists_per_user:
        return 0

    top_interactions = sorted(
        interactions,
        key=lambda interaction: int(interaction["plays"]),
        reverse=True,
    )[:max_artists_per_user]

    for rank, interaction in enumerate(top_interactions, start=1):
        plays = int(interaction["plays"])
        writer.writerow(
            {
                "user_id": user_id,
                "rank_for_user": rank,
                "artist_name": interaction["artist_name"],
                "normalized_artist": interaction["normalized_artist"],
                "plays": plays,
                "weight": round(math.log1p(plays), 6),
                "matched_tracks_count": interaction["matched_tracks_count"],
            }
        )

    return len(top_interactions)


def prepare_lastfm_data(args: argparse.Namespace) -> dict[str, object]:
    print("=" * 70)
    print("LAST.FM DATA PREPARATION")
    print("=" * 70)

    print("\n[1] Loading Spotify artist index...")
    artist_index = build_spotify_artist_index(args.spotify_path)
    print(f"    - Matched Spotify artist names: {len(artist_index)}")

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.summary_path.parent.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    bad_rows = 0
    matched_rows = 0
    skipped_low_plays = 0
    users_seen = 0
    eligible_users = 0
    interactions_written = 0
    matched_artist_counter: Counter[str] = Counter()

    current_user_id: str | None = None
    current_user_interactions: list[dict[str, object]] = []

    def flush_current_user(writer: csv.DictWriter) -> bool:
        nonlocal current_user_id
        nonlocal current_user_interactions
        nonlocal eligible_users
        nonlocal interactions_written

        if current_user_id is None:
            return False

        written = write_user_interactions(
            writer=writer,
            user_id=current_user_id,
            interactions=current_user_interactions,
            min_artists_per_user=args.min_artists_per_user,
            max_artists_per_user=args.max_artists_per_user,
        )

        if written:
            eligible_users += 1
            interactions_written += written

        current_user_id = None
        current_user_interactions = []

        return bool(args.max_users and eligible_users >= args.max_users)

    print("\n[2] Streaming Last.fm interactions...")
    with args.lastfm_path.open("r", encoding="utf-8", errors="replace", newline="") as input_file:
        with args.output_path.open("w", encoding="utf-8", newline="") as output_file:
            reader = csv.reader(input_file, delimiter="\t")
            writer = csv.DictWriter(
                output_file,
                fieldnames=[
                    "user_id",
                    "rank_for_user",
                    "artist_name",
                    "normalized_artist",
                    "plays",
                    "weight",
                    "matched_tracks_count",
                ],
            )
            writer.writeheader()

            for parts in reader:
                if args.max_rows and total_rows >= args.max_rows:
                    break

                total_rows += 1
                if len(parts) != 4:
                    bad_rows += 1
                    continue

                user_id, _artist_mbid, artist_name, raw_plays = parts
                if current_user_id is None:
                    current_user_id = user_id
                    users_seen += 1
                elif user_id != current_user_id:
                    if flush_current_user(writer):
                        break
                    current_user_id = user_id
                    users_seen += 1

                try:
                    plays = int(raw_plays)
                except ValueError:
                    bad_rows += 1
                    continue

                if plays < args.min_plays:
                    skipped_low_plays += 1
                    continue

                normalized_artist = normalize_artist(artist_name)
                spotify_artist = artist_index.get(normalized_artist)
                if spotify_artist is None:
                    continue

                matched_rows += 1
                matched_artist_counter[normalized_artist] += 1
                current_user_interactions.append(
                    {
                        "artist_name": artist_name,
                        "normalized_artist": normalized_artist,
                        "plays": plays,
                        "matched_tracks_count": spotify_artist["track_count"],
                    }
                )

                if total_rows % 1_000_000 == 0:
                    print(
                        "    - Read "
                        f"{total_rows:,} rows, matched {matched_rows:,}, "
                        f"eligible users {eligible_users:,}"
                    )

            flush_current_user(writer)

    summary = {
        "spotify_path": str(args.spotify_path),
        "lastfm_path": str(args.lastfm_path),
        "output_path": str(args.output_path),
        "total_rows_read": total_rows,
        "bad_rows": bad_rows,
        "users_seen": users_seen,
        "eligible_users_written": eligible_users,
        "matched_rows": matched_rows,
        "matched_row_rate": round(matched_rows / total_rows, 6) if total_rows else 0,
        "interactions_written": interactions_written,
        "unique_matched_artists": len(matched_artist_counter),
        "min_plays": args.min_plays,
        "min_artists_per_user": args.min_artists_per_user,
        "max_artists_per_user": args.max_artists_per_user,
        "max_rows": args.max_rows,
        "max_users": args.max_users,
        "top_matched_artists": matched_artist_counter.most_common(20),
    }

    with args.summary_path.open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, ensure_ascii=False, indent=2)

    print("\n[3] Done")
    print(f"    - Rows read: {total_rows:,}")
    print(f"    - Matched rows: {matched_rows:,}")
    print(f"    - Eligible users exported: {eligible_users:,}")
    print(f"    - Interactions written: {interactions_written:,}")
    print(f"    - Output: {args.output_path}")
    print(f"    - Summary: {args.summary_path}")

    return summary


if __name__ == "__main__":
    prepare_lastfm_data(parse_args())
