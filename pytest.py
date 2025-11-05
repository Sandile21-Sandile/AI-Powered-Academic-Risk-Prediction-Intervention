import numpy as np
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.datasets import load_iris
from sklearn.tree import DecisionTreeClassifier

# Load sample dataset
iris = load_iris()
X = iris.data
y = iris.target

# Create model
model = DecisionTreeClassifier()

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
# For multiclass targets use macro/micro/weighted variants of precision/recall/f1
# and use roc_auc_ovr or roc_auc_ovo for multiclass ROC-AUC.
scoring = ['accuracy', 'precision_macro', 'recall_macro', 'f1_macro', 'roc_auc_ovr']
scores = cross_validate(model, X, y, cv=cv, scoring=scoring, return_train_score=False)
for metric in scoring:
    mean = np.nanmean(scores[f'test_{metric}'])
    std = np.nanstd(scores[f'test_{metric}'])
    print(f"{metric}: {mean:.4f} ± {std:.4f}")