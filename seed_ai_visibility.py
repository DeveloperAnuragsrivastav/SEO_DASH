from __future__ import annotations
import os
import uuid
from datetime import date
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.models.client import Client
from app.models.ai_prompt import AiPrompt
from app.models.ai_mention import AiMention
from app.models.ranking import Ranking
from app.models.keyword import Keyword
from app.models.enums import AiPlatform, AiMentionSource

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ez_rankings")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed_ai_visibility():
    db = SessionLocal()
    try:
        from app.models.enums import ClientStatus
        client = db.execute(select(Client).where(Client.status == ClientStatus.active)).scalars().first()
        if not client:
            print("No active client found. Creating a default one for seeding.")
            from app.models.account import Account
            acc = db.execute(select(Account)).scalars().first()
            if not acc:
                acc = Account(name="Default Agency Account")
                db.add(acc)
                db.flush()
                
            client = Client(
                account_id=acc.id,
                name="Seeded Test Agency",
                domain="example.com",
                business_type="local",
                status=ClientStatus.active,
                locale="en-US",
                package_keywords=10,
                onboarded_at=date(2026, 1, 1)
            )
            db.add(client)
            db.flush()

        target_date = date(2026, 8, 15)

        print(f"Seeding AI Visibility for client: {client.name} ({client.id})")

        # 1. Create Prompts
        prompts = [
            AiPrompt(client_id=client.id, prompt_text="best seo agency in new york", is_active=True, added_at=date(2026, 8, 1)),
            AiPrompt(client_id=client.id, prompt_text="top local seo services near me", is_active=True, added_at=date(2026, 8, 1)),
            AiPrompt(client_id=client.id, prompt_text="who can help with my google business profile", is_active=True, added_at=date(2026, 8, 1)),
            AiPrompt(client_id=client.id, prompt_text="ez rankings reviews", is_active=True, added_at=date(2026, 8, 1)),
            AiPrompt(client_id=client.id, prompt_text="affordable seo packages for small business", is_active=True, added_at=date(2026, 8, 1))
        ]
        db.add_all(prompts)
        db.flush()

        # 2. Create Mentions
        # Let's say out of 5 prompts, ChatGPT mentioned us 3 times, Claude 1 time, Gemini 2 times, Perplexity 4 times
        mentions_data = [
            (prompts[0], AiPlatform.chatgpt, True, [{"url": "https://ezrankings.com", "mentions": 1}, {"url": "https://ezrankings.com/services", "mentions": 1}]),
            (prompts[1], AiPlatform.chatgpt, True, [{"url": "https://ezrankings.com/local-seo", "mentions": 1}]),
            (prompts[2], AiPlatform.chatgpt, True, None),
            (prompts[3], AiPlatform.chatgpt, False, None),
            (prompts[4], AiPlatform.chatgpt, False, None),
            
            (prompts[0], AiPlatform.claude, True, [{"url": "https://ezrankings.com", "mentions": 2}]),
            (prompts[1], AiPlatform.claude, False, None),
            (prompts[2], AiPlatform.claude, False, None),
            (prompts[3], AiPlatform.claude, False, None),
            (prompts[4], AiPlatform.claude, False, None),

            (prompts[0], AiPlatform.gemini, True, [{"url": "https://ezrankings.com/about", "mentions": 1}]),
            (prompts[1], AiPlatform.gemini, True, [{"url": "https://ezrankings.com/local-seo", "mentions": 1}]),
            (prompts[2], AiPlatform.gemini, False, None),
            (prompts[3], AiPlatform.gemini, False, None),
            (prompts[4], AiPlatform.gemini, False, None),

            (prompts[0], AiPlatform.perplexity, True, [{"url": "https://ezrankings.com", "mentions": 1}]),
            (prompts[1], AiPlatform.perplexity, True, [{"url": "https://ezrankings.com/local-seo", "mentions": 2}]),
            (prompts[2], AiPlatform.perplexity, True, [{"url": "https://ezrankings.com/contact", "mentions": 1}]),
            (prompts[3], AiPlatform.perplexity, True, [{"url": "https://ezrankings.com/reviews", "mentions": 1}]),
            (prompts[4], AiPlatform.perplexity, False, None)
        ]

        for p, plat, ment, pages in mentions_data:
            m = AiMention(
                client_id=client.id,
                prompt_id=p.id,
                platform=plat,
                captured_on=target_date,
                mentioned=ment,
                cited_pages=pages,
                source=AiMentionSource.llm_responses_custom
            )
            db.add(m)

        # 3. Update Rankings for AI Overview
        # Get some keywords and set ai_overview_present=True
        kws = db.execute(select(Keyword).where(Keyword.client_id == client.id).limit(3)).scalars().all()
        if not kws:
            print("No keywords found. Creating dummy keywords and rankings.")
            kw1 = Keyword(client_id=client.id, term="test seo agency", added_at=date(2026, 8, 1))
            kw2 = Keyword(client_id=client.id, term="best local seo", added_at=date(2026, 8, 1))
            db.add_all([kw1, kw2])
            db.flush()
            from app.models.enums import RankingSource
            r1 = Ranking(keyword_id=kw1.id, captured_on=target_date, position=2, url="https://ezrankings.com", source=RankingSource.api, ai_overview_present=True)
            r2 = Ranking(keyword_id=kw2.id, captured_on=target_date, position=5, url="https://ezrankings.com", source=RankingSource.api, ai_overview_present=True)
            db.add_all([r1, r2])
            kws = [kw1, kw2]

        if kws:
            kw_ids = [kw.id for kw in kws]
            db.execute(
                update(Ranking).where(Ranking.keyword_id.in_(kw_ids)).values(ai_overview_present=True)
            )
            print(f"Set ai_overview_present=True for {len(kws)} keywords.")

        db.commit()
        print("Successfully seeded AI Visibility data.")

    except Exception as e:
        db.rollback()
        print(f"Error seeding AI visibility data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_ai_visibility()
