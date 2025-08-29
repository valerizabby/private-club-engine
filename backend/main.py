import time
import logging
from sqlite3 import OperationalError

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.future import select

from models.request import TelegramIdRequest, GoToRequest, SpendRequest
from models.tables import User, Session, Base, Stat, UserStat
from db_init import engine, get_session
from sqlalchemy.ext.asyncio import AsyncSession
import json
from datetime import date
from pathlib import Path
import traceback

# логгер
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# наименование стартовой сцены игры
START_SCENE_ID = "scene1"
# переменная для хранения пассажей (сцен) игры
PASSAGES = {}
# размер ежедневного бонуса
bonus_amount = 5
base_dir = Path(__file__).parent
# локация пассажей
passages_path = base_dir / "parser" / "passages.json"
# Инициализация предопределённых стат
PREDEFINED_STATS = [
    {"code": "quiet", "name": "Тихоня"},
    {"code": "rebel", "name": "Бунтарка"},
    {"code": "reputation", "name": "Репутация"},
]
story_id = "default"

@app.on_event("startup")
async def startup():
    global PASSAGES
    logger.info("⏳ Запуск приложения и инициализация таблиц")
    max_tries = 10
    for i in range(max_tries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Таблицы успешно созданы")
            break
        except OperationalError:
            logger.warning(f"⏳ DB not ready, waiting... ({i + 1}/{max_tries})")
            time.sleep(2)
    else:
        logger.error("❌ Database not available after retries")
        raise RuntimeError("Database not available after retries")

    logger.info(f"📖 Загружаем историю из {passages_path}")
    with open(passages_path, encoding="utf-8") as f:
        PASSAGES = json.load(f)
    logger.info(f"✅ Загружено {len(PASSAGES)} сцен")

    # 💾 Инициализация предопределённых стат
    PREDEFINED_STATS = [
        {"code": "quiet", "name": "Тихоня"},
        {"code": "rebel", "name": "Бунтарка"},
        {"code": "reputation", "name": "Репутация"},
    ]
    story_id = "default"

    async with engine.begin() as conn:
        for stat_def in PREDEFINED_STATS:
            result = await conn.execute(
                select(Stat).where(
                    Stat.code == stat_def["code"],
                    Stat.story_id == story_id
                )
            )
            if result.scalar_one_or_none() is None:
                await conn.execute(
                    Stat.__table__.insert().values(
                        code=stat_def["code"],
                        name=stat_def["name"],
                        story_id=story_id
                    )
                )
                logger.info(f"🆕 Стата '{stat_def['code']}' создана")
            else:
                logger.info(f"✅ Стата '{stat_def['code']}' уже есть")

@app.post("/init_user")
async def init_user(req: TelegramIdRequest, db: AsyncSession = Depends(get_session)):
    logger.info(f"👤 Инициализация пользователя: {req.telegram_id}")
    result = await db.execute(select(User).where(User.telegram_id == req.telegram_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(telegram_id=req.telegram_id, balance=10)
        db.add(user)
        await db.commit()
        logger.info(f"🆕 Новый пользователь зарегистрирован: {req.telegram_id}")

    return {"status": "ok"}


@app.post("/start")
async def start_game(req: TelegramIdRequest, db: AsyncSession = Depends(get_session)):
    logger.info(f"▶️ Старт игры для пользователя: {req.telegram_id}")
    telegram_id = req.telegram_id
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.info(f"🔧 Регистрируем нового пользователя: {telegram_id}")
        user = User(telegram_id=telegram_id)
        db.add(user)
        await db.flush()

        session = Session(user_id=user.id, current_scene_id=START_SCENE_ID)
        db.add(session)
    else:
        result = await db.execute(select(Session).where(Session.user_id == user.id))
        session = result.scalar_one_or_none()
        if session is None:
            session = Session(user_id=user.id, current_scene_id=START_SCENE_ID)
            db.add(session)

    await db.commit()
    return {"scene_id": session.current_scene_id, "balance": user.balance}


@app.post("/progress")
async def get_progress(req: TelegramIdRequest, db: AsyncSession = Depends(get_session)):
    telegram_id = req.telegram_id
    logger.info(f"📥 Запрос прогресса для: {telegram_id}")
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(select(Session).where(Session.user_id == user.id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info(f"📤 Отдаем сцену: {session.current_scene_id}")
    scene = PASSAGES.get(session.current_scene_id)
    if not scene:
        raise HTTPException(status_code=500, detail="Scene not found")

    return {
        **scene,
        "balance": user.balance
    }

@app.post("/go_to")
async def go_to_scene(req: GoToRequest, db: AsyncSession = Depends(get_session)):
    telegram_id = req.telegram_id
    target_scene_id = req.target_scene_id
    logger.info(f"➡️ Переход к сцене {target_scene_id} от пользователя {telegram_id}")

    try:
        # 1. Получаем пользователя
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # 2. Получаем сессию
        result = await db.execute(select(Session).where(Session.user_id == user.id))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # 3. Проверяем текущую сцену
        current_scene_id = session.current_scene_id
        current_scene = PASSAGES.get(current_scene_id)
        if not current_scene:
            raise HTTPException(status_code=500, detail="Current scene not found")

        # 4. Ищем выбор
        current_scene_id = session.current_scene_id
        current_scene = PASSAGES.get(current_scene_id)
        if not current_scene:
            raise HTTPException(status_code=500, detail="Current scene not found")

        matching_choice = next((c for c in current_scene.get("choices", []) if c["target"] == target_scene_id), None)

        if not matching_choice:
            # проверим, что это переход по autonext
            if current_scene.get("autonext") == target_scene_id:
                logger.info(f"🔄 Переход по autonext со сцены {current_scene_id} → {target_scene_id}")
            else:
                raise HTTPException(status_code=400, detail="Invalid choice")

        # 5. Применяем stat
        if matching_choice and "stat" in matching_choice:
            stat_code = matching_choice["stat"]
            logger.info(f"📈 Добавляем очко статы '{stat_code}' пользователю {telegram_id}")
            story_id = "default"

            stat_result = await db.execute(select(Stat).where(Stat.code == stat_code, Stat.story_id == story_id))
            stat = stat_result.scalar_one_or_none()

            if stat:
                user_stat_result = await db.execute(
                    select(UserStat).where(UserStat.user_id == user.id, UserStat.stat_id == stat.id)
                )
                user_stat = user_stat_result.scalar_one_or_none()

                if user_stat:
                    user_stat.value += 1
                    logger.info(f"🔄 Стата {stat_code} обновлена до {user_stat.value}")
                else:
                    db.add(UserStat(user_id=user.id, stat_id=stat.id, value=1))
                    logger.info(f"🆕 Стата {stat_code} создана для пользователя")
            else:
                logger.warning(f"⚠️ Стата '{stat_code}' не найдена в таблице stat")

        # 6. Обновляем сцену
        session.current_scene_id = target_scene_id
        await db.commit()

        # 7. Загружаем следующую сцену
        next_scene = PASSAGES.get(target_scene_id)
        if not next_scene:
            raise HTTPException(status_code=500, detail="Next scene not found")

        return {
            **next_scene,
            "balance": user.balance,
        }

    except Exception as e:
        logger.error("❌ Ошибка в /go_to:\n" + traceback.format_exc())
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/daily_bonus")
async def daily_bonus(req: TelegramIdRequest, db: AsyncSession = Depends(get_session)):
    telegram_id = req.telegram_id
    logger.info(f"🎁 Проверка бонуса для {telegram_id}")
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    today = date.today()
    if user.last_bonus_at == today:
        logger.info("🎁 Бонус уже получен сегодня")
        return {"received": False, "balance": user.balance}

    user.balance += bonus_amount
    user.last_bonus_at = today
    await db.commit()
    logger.info(f"🎉 Бонус выдан: +{bonus_amount}")

    return {"received": True, "balance": user.balance}


@app.post("/spend")
async def spend_crystals(req: SpendRequest, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(User).where(User.telegram_id == req.telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.balance < req.amount:
        logger.warning(f"❌ Недостаточно кристаллов у {req.telegram_id}")
        raise HTTPException(status_code=400, detail="Not enough crystals")

    user.balance -= req.amount
    await db.commit()
    logger.info(f"💎 Списано {req.amount} кристаллов у {req.telegram_id}")

    return {"balance": user.balance}


@app.post("/reset_progress")
async def reset_progress(req: TelegramIdRequest, db: AsyncSession = Depends(get_session)):
    logger.info(f"🔄 Сброс прогресса для: {req.telegram_id}")

    # 1. Находим пользователя
    result = await db.execute(select(User).where(User.telegram_id == req.telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Получаем сессию
    result = await db.execute(select(Session).where(Session.user_id == user.id))
    session = result.scalar_one_or_none()

    if session:
        session.current_scene_id = START_SCENE_ID
    else:
        # Если сессии нет — создаём её с нуля
        session = Session(user_id=user.id, current_scene_id=START_SCENE_ID)
        db.add(session)

    # 3. (опционально) сбрасываем все значения UserStat
    user_stats_result = await db.execute(select(UserStat).where(UserStat.user_id == user.id))
    for user_stat in user_stats_result.scalars():
        user_stat.value = 0

    await db.commit()

    logger.info(f"🔁 Прогресс сброшен для {req.telegram_id}")
    return {"scene_id": session.current_scene_id, "balance": user.balance}