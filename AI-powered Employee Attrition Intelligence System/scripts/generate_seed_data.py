"""
Seed Data Generator.
Generates realistic synthetic employee data for:
1. ML model training (CSV output)
2. Database seeding (SQL/SQLAlchemy inserts)

Usage:
    python scripts/generate_seed_data.py --n 2000 --output data/training_data.csv
    python scripts/generate_seed_data.py --seed-db
"""

from __future__ import annotations
import random
import uuid
import argparse
import asyncio
from datetime import date, timedelta
from typing import List, Dict

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
rng = np.random.default_rng(42)


DEPARTMENTS = [
    "Engineering", "Product", "Sales", "Marketing", "HR",
    "Finance", "Operations", "Customer Success", "Data", "Design",
]

JOB_ROLES = {
    "Engineering": ["Software Engineer", "Senior Engineer", "Staff Engineer", "DevOps Engineer", "QA Engineer"],
    "Product": ["Product Manager", "Senior PM", "Product Analyst", "UX Researcher"],
    "Sales": ["Sales Rep", "Account Executive", "Sales Manager", "Business Development"],
    "Marketing": ["Marketing Manager", "Growth Marketer", "Content Strategist", "SEO Specialist"],
    "HR": ["HR Business Partner", "Recruiter", "L&D Manager", "HR Analyst"],
    "Finance": ["Financial Analyst", "Senior Analyst", "Finance Manager", "Controller"],
    "Operations": ["Operations Manager", "Process Analyst", "Supply Chain Lead"],
    "Customer Success": ["CSM", "Senior CSM", "CS Director", "Support Engineer"],
    "Data": ["Data Analyst", "Data Scientist", "ML Engineer", "Analytics Engineer"],
    "Design": ["UX Designer", "Product Designer", "Visual Designer", "Design Lead"],
}

JOB_LEVELS = ["Junior", "Mid", "Senior", "Lead", "Manager", "Director"]
INCOME_RANGE = {
    "Junior": (2500, 4500), "Mid": (4500, 7000), "Senior": (7000, 12000),
    "Lead": (10000, 16000), "Manager": (12000, 20000), "Director": (18000, 30000),
}

TEAM_IDS = [f"team_{i:03d}" for i in range(1, 21)]


def _correlated_attrition(row: Dict) -> int:
    """
    Generate attrition label with realistic correlations.
    High overtime, low satisfaction, low income, high stagnation → more likely to leave.
    """
    prob = 0.15  # base rate

    # Strong signals
    if row["overtime_ratio"] > 0.35:
        prob += 0.20
    if row["job_satisfaction"] < 2.5:
        prob += 0.18
    if row["work_life_balance"] < 2.0:
        prob += 0.15
    if row["years_since_last_promotion"] > 4 and row["years_at_company"] > 3:
        prob += 0.12
    if row["income_adequacy_ratio"] < 0.8:
        prob += 0.10
    if row["burnout_signal"] > 7:
        prob += 0.15

    # Protective signals
    if row["job_satisfaction"] >= 4.0:
        prob -= 0.10
    if row["years_with_curr_manager"] >= 3.0:
        prob -= 0.05
    if row["promotion_velocity"] <= 1.5:
        prob -= 0.05
    if row["performance_rating"] >= 4.5:
        prob -= 0.05

    prob = max(0.02, min(0.95, prob))
    return int(rng.random() < prob)


def _correlated_promotion(row: Dict) -> int:
    """Promotion label correlated with performance and tenure."""
    prob = 0.15
    if row["performance_rating"] >= 4.0:
        prob += 0.20
    if row["leadership_score"] >= 7.5:
        prob += 0.15
    if row["years_at_company"] >= 2.0:
        prob += 0.10
    if row["task_efficiency_score"] >= 0.85:
        prob += 0.10
    if row["training_hours"] >= 40:
        prob += 0.08
    if row["career_stagnation_score"] >= 7.0:
        prob += 0.12
    if row["years_since_last_promotion"] < 1.0:
        prob -= 0.20
    prob = max(0.02, min(0.90, prob))
    return int(rng.random() < prob)


def generate_employee_row(employee_id: int) -> Dict:
    dept = random.choice(DEPARTMENTS)
    roles = JOB_ROLES.get(dept, ["Analyst"])
    role = random.choice(roles)
    level = random.choice(JOB_LEVELS)
    income_min, income_max = INCOME_RANGE[level]
    income = rng.uniform(income_min, income_max)

    level_num = JOB_LEVELS.index(level) + 1
    expected_income = {1: 3000, 2: 5000, 3: 8000, 4: 10000, 5: 13000, 6: 18000}.get(level_num, 5000)
    income_adequacy = min(income / expected_income, 3.0)

    years_at_company = rng.exponential(4.0)
    years_at_company = float(np.clip(years_at_company, 0.25, 25.0))
    years_since_promo = rng.uniform(0, min(years_at_company, 8))
    years_with_manager = rng.uniform(0, min(years_at_company, 6))
    years_in_role = rng.uniform(0, min(years_at_company, 5))

    performance = float(np.clip(rng.normal(3.2, 0.8), 1, 5))
    job_sat = float(np.clip(rng.normal(3.0, 1.0), 1, 5))
    wlb = float(np.clip(rng.normal(3.0, 0.9), 1, 5))
    env_sat = float(np.clip(rng.normal(3.1, 0.9), 1, 5))
    rel_sat = float(np.clip(rng.normal(3.2, 0.8), 1, 5))

    overtime_hours = float(np.clip(rng.exponential(20), 0, 120))
    standard_hours = 160.0
    overtime_ratio = min(overtime_hours / standard_hours, 2.0)
    attendance_rate = float(np.clip(rng.normal(0.93, 0.07), 0.60, 1.0))

    workload = float(np.clip(rng.normal(5.5, 1.8), 1, 10))
    team_health = float(np.clip(rng.normal(6.5, 1.5), 1, 10))
    collab = float(np.clip(rng.normal(6.8, 1.3), 1, 10))

    tasks_assigned = int(rng.integers(5, 60))
    missed = int(rng.integers(0, max(1, int(tasks_assigned * 0.3))))
    completed = tasks_assigned - missed
    overdue_ratio = min(missed / max(tasks_assigned, 1), 1.0)
    task_efficiency = max(0.0, min(1.0, completed / max(tasks_assigned, 1) - overdue_ratio * 0.3))

    leadership = float(np.clip(rng.normal(5.5, 2.0), 1, 10))
    promo_velocity = float(np.clip(rng.exponential(3.0), 0.5, 10))
    training_hours = float(np.clip(rng.exponential(20), 0, 120))

    # Derived features
    deadline_failure = missed / max(tasks_assigned, 1)
    promo_gap = years_since_promo / max(promo_velocity, 0.5)
    workload_pressure = min(workload * 0.4 + overtime_ratio * 10 * 0.35 + overdue_ratio * 10 * 0.25, 10.0)
    stability = min((years_at_company / 15) * 10 * 0.6 + (years_with_manager / 10) * 10 * 0.4, 10.0)
    burnout = min(((5 - wlb) / 4) * 10 * 0.30 + overtime_ratio * 10 * 0.25 + workload_pressure * 0.25
                  + ((5 - job_sat) / 4) * 10 * 0.10 + ((5 - env_sat) / 4) * 10 * 0.10, 10.0)
    sat_composite = np.mean([job_sat, wlb, env_sat, rel_sat])
    perf_trend = (performance / 5) - (workload_pressure / 10) * 0.5
    stagnation = min((years_in_role / 8) * 10 * 0.4 + (years_since_promo / 5) * 10 * 0.6, 10.0)
    engagement = min(((sat_composite - 1) / 4) * 10 * 0.40 + max(perf_trend, 0) * 10 * 0.30
                     + ((collab - 1) / 9) * 10 * 0.20 + min(training_hours / 40, 1) * 10 * 0.10, 10.0)

    row = {
        "employee_id": f"EMP{employee_id:05d}",
        "age": int(rng.integers(22, 58)),
        "department": dept,
        "job_role": role,
        "job_level": level,
        "monthly_income": round(income, 2),
        "years_at_company": round(years_at_company, 2),
        "years_since_last_promotion": round(years_since_promo, 2),
        "years_with_curr_manager": round(years_with_manager, 2),
        "years_in_current_role": round(years_in_role, 2),
        "performance_rating": round(performance, 2),
        "job_satisfaction": round(job_sat, 2),
        "work_life_balance": round(wlb, 2),
        "environment_satisfaction": round(env_sat, 2),
        "relationship_satisfaction": round(rel_sat, 2),
        "overtime_hours": round(overtime_hours, 2),
        "standard_hours": standard_hours,
        "attendance_rate": round(attendance_rate, 4),
        "workload_score": round(workload, 2),
        "team_health_score": round(team_health, 2),
        "collaboration_score": round(collab, 2),
        "tasks_completed": completed,
        "tasks_assigned": tasks_assigned,
        "missed_deadlines": missed,
        "overdue_task_ratio": round(overdue_ratio, 4),
        "leadership_score": round(leadership, 2),
        "promotion_velocity": round(promo_velocity, 2),
        "training_hours": round(training_hours, 2),
        # Derived
        "overtime_ratio": round(overtime_ratio, 4),
        "deadline_failure_rate": round(deadline_failure, 4),
        "promotion_gap_years": round(promo_gap, 4),
        "workload_pressure_score": round(workload_pressure, 4),
        "stability_score": round(stability, 4),
        "burnout_signal": round(burnout, 4),
        "satisfaction_composite": round(float(sat_composite), 4),
        "performance_trend": round(float(perf_trend), 4),
        "career_stagnation_score": round(stagnation, 4),
        "income_adequacy_ratio": round(income_adequacy, 4),
        "task_efficiency_score": round(task_efficiency, 4),
        "engagement_score": round(engagement, 4),
        "team_id": random.choice(TEAM_IDS),
    }

    row["attrition"] = _correlated_attrition(row)
    row["promotion"] = _correlated_promotion(row)
    return row


def generate_training_dataframe(n_employees: int = 2000) -> pd.DataFrame:
    """Generate a synthetic training dataset."""
    rows = [generate_employee_row(i) for i in range(1, n_employees + 1)]
    df = pd.DataFrame(rows)
    print(f"Generated {len(df)} rows | Attrition rate: {df['attrition'].mean():.2%} | Promotion rate: {df['promotion'].mean():.2%}")
    return df


async def seed_database(n: int = 100) -> None:
    """Insert synthetic employees into the database."""
    import os
    os.makedirs("./logs", exist_ok=True)

    from app.db.session import AsyncSessionLocal, init_db
    from app.models.employee import Employee
    from app.models.metrics import EmployeeMetrics

    await init_db()

    rows = [generate_employee_row(i) for i in range(1, n + 1)]

    async with AsyncSessionLocal() as session:
        for row in rows:
            hire_date = date.today() - timedelta(days=int(row["years_at_company"] * 365))
            emp = Employee(
                id=uuid.uuid4(),
                employee_code=row["employee_id"],
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                email=fake.unique.email(),
                age=row["age"],
                department=row["department"],
                job_role=row["job_role"],
                job_level=row["job_level"],
                monthly_income=row["monthly_income"],
                hire_date=hire_date,
                years_at_company=row["years_at_company"],
                years_since_last_promotion=row["years_since_last_promotion"],
                years_with_curr_manager=row["years_with_curr_manager"],
                years_in_current_role=row["years_in_current_role"],
                team_id=row["team_id"],
                is_active=True,
            )
            metrics = EmployeeMetrics(
                id=uuid.uuid4(),
                employee_id=emp.id,
                snapshot_date=date.today(),
                performance_rating=row["performance_rating"],
                job_satisfaction=row["job_satisfaction"],
                work_life_balance=row["work_life_balance"],
                environment_satisfaction=row["environment_satisfaction"],
                relationship_satisfaction=row["relationship_satisfaction"],
                overtime_hours=row["overtime_hours"],
                standard_hours=row["standard_hours"],
                attendance_rate=row["attendance_rate"],
                workload_score=row["workload_score"],
                team_health_score=row["team_health_score"],
                collaboration_score=row["collaboration_score"],
                tasks_completed=row["tasks_completed"],
                tasks_assigned=row["tasks_assigned"],
                missed_deadlines=row["missed_deadlines"],
                overdue_task_ratio=row["overdue_task_ratio"],
                leadership_score=row["leadership_score"],
                promotion_velocity=row["promotion_velocity"],
                training_hours=row["training_hours"],
            )
            session.add(emp)
            session.add(metrics)

        await session.commit()
    print(f"Seeded {n} employees into database.")


if __name__ == "__main__":
    import os

    parser = argparse.ArgumentParser(description="SyncVerse Seed Data Generator")
    parser.add_argument("--n", type=int, default=2000, help="Number of employees to generate")
    parser.add_argument("--output", type=str, default="./data/training_data.csv", help="Output CSV path")
    parser.add_argument("--seed-db", action="store_true", help="Seed the database instead of CSV")
    args = parser.parse_args()

    if args.seed_db:
        asyncio.run(seed_database(n=args.n))
    else:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        df = generate_training_dataframe(n_employees=args.n)
        df.to_csv(args.output, index=False)
        print(f"Training data saved to {args.output}")
