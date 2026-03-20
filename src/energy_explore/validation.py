import numpy as np
from typing import Dict, List

def monthly_indices() -> List[np.ndarray]:
    """Returns a list of 12 index arrays, one for each month (assuming non-leap year)."""
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    indices = []
    current = 0
    for days in days_in_month:
        start = current * 24
        end = (current + days) * 24
        indices.append(np.arange(start, end))
        current += days
    return indices

def compute_monthly_means(y: np.ndarray) -> np.ndarray:
    """Computes the 12 monthly means of an 8760-length hourly series."""
    idxs = monthly_indices()
    return np.array([y[idx].mean() for idx in idxs], dtype=np.float32)

def validation_metrics(arrays: Dict[str, np.ndarray], targets: Dict[str, np.ndarray]) -> Dict[str, float]:
    """
    Computes MBE, RMSE, Lag-1 Autocorr, Variance Ratio, and Skewness for synthetic vs target climatology.
    """
    metrics = {}
    
    # Mapping our internal array keys to target climatology keys
    keys = [
        ("ghi", "monthly_ghi_means"),
        ("temp", "monthly_temp_means"),
        ("wind", "monthly_wind_means")
    ]
    
    try:
        for array_key, target_key in keys:
            if array_key not in arrays or target_key not in targets:
                continue
                
            y_hourly = arrays[array_key]
            y_target = targets[target_key] # This is length 12
            
            y_monthly = compute_monthly_means(y_hourly)
            
            # 1. MBE (Mean Bias Error)
            mbe = (y_monthly - y_target)
            metrics[f"{array_key}_monthly_mbe"] = mbe
            
            # 2. RMSE (Root Mean Square Error) of monthly means
            rmse = np.sqrt(np.mean(mbe**2))
            metrics[f"{array_key}_monthly_rmse"] = float(rmse)
            
            # 3. Lag-1 Autocorrelation (Persistence)
            # corr = cov(x, y) / (std(x) * std(y))
            x = y_hourly[:-1]
            y = y_hourly[1:]
            
            try:
                if np.std(x) == 0 or np.std(y) == 0:
                    autocorr = 0.0
                else:
                    autocorr = np.corrcoef(x, y)[0, 1]
            except:
                autocorr = 0.0
                
            metrics[f"{array_key}_lag1_autocorr"] = float(autocorr)
            
            # 4. Variance Ratio (Synthetic Var / Target Var) - Approximate
            # Since target is only monthly means, we compare monthly variance
            if np.var(y_target) > 0:
                metrics[f"{array_key}_variance_ratio"] = float(np.var(y_monthly) / np.var(y_target))
            else:
                metrics[f"{array_key}_variance_ratio"] = 1.0
                
            # 5. Skewness
            if np.std(y_hourly) > 0:
                m3 = np.mean((y_hourly - np.mean(y_hourly))**3)
                skew = m3 / (np.std(y_hourly)**3)
                metrics[f"{array_key}_skewness"] = float(skew)
            else:
                metrics[f"{array_key}_skewness"] = 0.0
                
    except Exception:
        # Return partial or empty dict on failure to avoid crashing the app
        return metrics
        
    return metrics
