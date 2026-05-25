# Employee Attrition Prediction (Machine Learning)

## Project Overview
This project builds a machine learning system to predict employee attrition using HR analytics data.  
The goal is to help HR departments identify employees at risk of leaving and enable proactive retention strategies.

---

## Business Problem
Employee turnover is costly and disruptive.  
By predicting attrition early, organizations can take preventive actions such as improving work conditions, compensation planning, or workload adjustments.

---

## Dataset
IBM HR Analytics Employee Attrition Dataset.

- 1470 employees
- Demographics, job roles, compensation, and satisfaction metrics

---

## Project Workflow
1. Data Cleaning & Preprocessing
2. Exploratory Data Analysis (EDA)
3. Feature Engineering & Multicollinearity Handling
4. Model Training & Comparison
5. Model Evaluation using ROC-AUC
6. Final Model Selection
7. Model Saving & Inference Example

---

## Models Evaluated
- Logistic Regression
- Random Forest
- XGBoost
- Gradient Boosting

Logistic Regression was selected as the final model due to its strong ROC-AUC performance and high interpretability, which is critical for HR decision-making.

---

## Key Insights
- Overtime significantly increases attrition risk.
- Early-career employees are more likely to leave.
- Monthly income and job level strongly influence retention.
- Certain job roles (e.g., Sales Representatives) show higher turnover.

---

## Example Prediction
The model estimates the probability of employee attrition and assigns a risk level:
