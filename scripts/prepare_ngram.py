"""Kiểm tra và xây chỉ mục FULLTEXT ngram trên MySQL 8."""

import argparse

from sqlalchemy import text

from app.core.database import engine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
    )
    args = parser.parse_args()

    with engine.connect() as connection:
        version = str(
            connection.scalar(
                text("SELECT VERSION()")
            )
        )

        if (
            "mariadb" in version.lower()
            or int(version.split(".")[0]) < 8
        ):
            raise SystemExit(
                "Cần MySQL 8 trở lên. "
                "MariaDB/XAMPP chỉ chạy chế độ demo LIKE."
            )

        token_size = connection.scalar(
            text(
                "SELECT @@GLOBAL.ngram_token_size"
            )
        )

        stopwords = connection.scalar(
            text(
                "SELECT @@GLOBAL.innodb_ft_enable_stopword"
            )
        )

        if token_size != 2 or stopwords:
            raise SystemExit(
                "Cấu hình mysqld: "
                "ngram_token_size=2 và "
                "innodb_ft_enable_stopword=OFF; "
                "khởi động lại MySQL trước."
            )

        ddl = connection.execute(
            text("SHOW CREATE TABLE memories")
        ).first()[1]

        print("MySQL:", version)
        print(
            "Có parser ngram:",
            "ngram" in ddl.lower(),
        )

        if not args.apply:
            print(
                "Muốn xây lại chỉ mục: "
                "python -m scripts.prepare_ngram --apply"
            )
            return

        connection.execute(
            text(
                "SET SESSION innodb_ft_enable_stopword=OFF"
            )
        )

        indexes = (
            connection.execute(
                text("SHOW INDEX FROM memories")
            )
            .mappings()
            .all()
        )

        clauses = []

        if any(
            row["Key_name"] == "ft_mem_search"
            for row in indexes
        ):
            clauses.append(
                "DROP INDEX ft_mem_search"
            )

        clauses += [
            (
                "MODIFY title VARCHAR(200) "
                "CHARACTER SET utf8mb4 "
                "COLLATE utf8mb4_0900_ai_ci "
                "NOT NULL"
            ),
            (
                "MODIFY place_name VARCHAR(255) "
                "CHARACTER SET utf8mb4 "
                "COLLATE utf8mb4_0900_ai_ci "
                "NOT NULL"
            ),
            (
                "ADD FULLTEXT INDEX ft_mem_search "
                "(title, place_name) "
                "WITH PARSER ngram"
            ),
        ]

        connection.execute(
            text(
                "ALTER TABLE memories "
                + ", ".join(clauses)
            )
        )

        connection.commit()

        print(
            "Đã xây chỉ mục FULLTEXT ngram. "
            "Dữ liệu ký ức được giữ nguyên."
        )


if __name__ == "__main__":
    main()