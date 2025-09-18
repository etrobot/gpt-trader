from __future__ import annotations
import logging
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
from utils import update_task_progress

logger = logging.getLogger(__name__)


def compute_factors(
    top_symbols: pd.DataFrame,
    history: Dict[str, pd.DataFrame],
    task_id: Optional[str] = None,
    selected_factors: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Compute comprehensive factors for crypto analysis via pluggable factor modules
    
    Excludes factors without values from final calculation to ensure data quality.
    """
    from factors import compute_all_factors, compute_selected_factors

    logger.info("Computing factors using modular plugins...")

    if task_id:
        update_task_progress(task_id, 0.7, "计算各类因子")

    # Filter history to only include top symbols
    filtered_history = {
        symbol: df
        for symbol, df in history.items()
        if symbol in top_symbols["symbol"].values
    }

    # Compute selected or all registered factor dataframes
    if selected_factors:
        factors_df = compute_selected_factors(
            filtered_history, top_symbols, selected_factors
        )
        logger.info(f"Computing selected factors: {selected_factors}")
    else:
        factors_df = compute_all_factors(filtered_history, top_symbols)
        logger.info("Computing all available factors")

    if factors_df is None or factors_df.empty:
        logger.warning("No factor data calculated")
        factors_df = pd.DataFrame({"symbol": list(filtered_history.keys())})

    result = factors_df

    # Add current price, symbol name and other basic info
    current_data = []
    for symbol in result["symbol"].tolist():
        df = filtered_history.get(symbol)
        if df is not None and not df.empty:
            # 确保DataFrame有正确的列名
            if "date" in df.columns:
                df = df.rename(columns={"date": "日期"})
            if "close" in df.columns:
                df = df.rename(columns={"close": "收盘"})
            if "change_pct" in df.columns:
                df = df.rename(columns={"change_pct": "涨跌幅"})

            # 检查必要的列是否存在
            required_columns = ["日期", "收盘", "涨跌幅"]
            if all(col in df.columns for col in required_columns):
                df_sorted = df.sort_values("日期")
                symbol_name = (
                    top_symbols[top_symbols["symbol"] == symbol]["name"].iloc[0]
                    if "name" in top_symbols.columns
                    and len(top_symbols[top_symbols["symbol"] == symbol]) > 0
                    else symbol
                )
                current_data.append(
                    {
                        "symbol": symbol,
                        "name": symbol_name,
                        "当前价格": float(df_sorted["收盘"].iloc[-1]),
                        "涨跌幅": (
                            float(df_sorted["涨跌幅"].iloc[-1])
                            if "涨跌幅" in df_sorted.columns
                            else 0
                        ),
                    }
                )
            else:
                # 如果缺少必要的列，使用默认值
                symbol_name = (
                    top_symbols[top_symbols["symbol"] == symbol]["name"].iloc[0]
                    if "name" in top_symbols.columns
                    and len(top_symbols[top_symbols["symbol"] == symbol]) > 0
                    else symbol
                )
                current_data.append(
                    {"symbol": symbol, "name": symbol_name, "当前价格": 0, "涨跌幅": 0}
                )

    current_df = pd.DataFrame(current_data)
    if not current_df.empty:
        result = result.merge(current_df, on="symbol", how="left")

    # Filter out factors with no values before computing scores
    result = _filter_valid_factors(result)
    
    # Filter out symbols that have no valid factor values
    result = _filter_symbols_without_factors(result)

    # Generic score computation: for any column ending with '因子', compute a percentile rank score with suffix '评分'
    score_columns = []
    for col in list(result.columns):
        if isinstance(col, str) and col.endswith("因子"):
            # Only compute score if factor has valid values
            if _has_valid_values(result[col]):
                score_col = col.replace("因子", "评分")
                try:
                    result[score_col] = result[col].rank(ascending=True, pct=True)
                    score_columns.append(score_col)
                    logger.info(f"Computed score for factor: {col}")
                except Exception as e:
                    logger.warning(f"Failed to compute score for factor {col}: {e}")
            else:
                logger.info(f"Skipping factor {col} - no valid values")

    # Composite score: average of all available score columns if any
    if score_columns:
        # Calculate composite score using mean of available scores (skipna=True)
        result["综合评分"] = result[score_columns].mean(axis=1, skipna=True)
        
        # Count how many valid scores each symbol has for better ranking
        result["有效因子数"] = result[score_columns].count(axis=1)
        
        # Sort by composite score (descending), then by number of valid factors (descending)
        result = result.sort_values(
            ["综合评分", "有效因子数"], 
            ascending=[False, False], 
            na_position='last'
        )
        
        # Remove the helper column
        result = result.drop(columns=["有效因子数"])
        
        logger.info(f"Computed composite score using {len(score_columns)} factor types")
        
        # Log symbols with missing scores
        missing_scores = result["综合评分"].isna().sum()
        if missing_scores > 0:
            logger.warning(f"{missing_scores} symbols have no valid factor scores")
    else:
        logger.warning("No factor scores computed - no valid factors found")

    if task_id:
        update_task_progress(task_id, 0.9, "计算因子评分")

    # Save evaluation results to local file for debugging
    try:
        import os
        debug_dir = "debug_output"
        if not os.path.exists(debug_dir):
            os.makedirs(debug_dir)
        
        # Save detailed debug information
        debug_file = os.path.join(debug_dir, "factor_evaluation_debug.csv")
        result.to_csv(debug_file, index=False, encoding='utf-8-sig')
        logger.info(f"Saved factor evaluation results to {debug_file}")
        
        # Save summary statistics
        summary_file = os.path.join(debug_dir, "factor_summary.txt")
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=== Factor Evaluation Summary ===\n")
            f.write(f"Total symbols processed: {len(result)}\n")
            f.write(f"Total columns: {len(result.columns)}\n")
            f.write(f"Columns: {list(result.columns)}\n\n")
            
            # Check for empty rows
            empty_rows = result.isnull().all(axis=1).sum()
            f.write(f"Completely empty rows: {empty_rows}\n")
            
            # Check for rows with missing factor values
            factor_cols = [col for col in result.columns if col.endswith("因子")]
            f.write(f"Factor columns: {factor_cols}\n")
            
            if factor_cols:
                rows_without_factors = result[factor_cols].isnull().all(axis=1).sum()
                f.write(f"Rows without any factor values: {rows_without_factors}\n")
                
                for col in factor_cols:
                    null_count = result[col].isnull().sum()
                    zero_count = (result[col] == 0).sum()
                    inf_count = np.isinf(result[col]).sum()
                    valid_count = result[col].notna().sum() - inf_count
                    f.write(f"  {col}: {null_count} nulls, {zero_count} zeros, {inf_count} infinites, {valid_count} valid values\n")
            
            # Check score columns
            score_cols = [col for col in result.columns if col.endswith("评分")]
            f.write(f"\nScore columns: {score_cols}\n")
            
            if score_cols:
                for col in score_cols:
                    null_count = result[col].isnull().sum()
                    f.write(f"  {col}: {null_count} nulls\n")
            
            # Show first few rows with issues
            f.write("\n=== Sample rows with missing data ===\n")
            if factor_cols:
                problematic_rows = result[result[factor_cols].isnull().any(axis=1)]
                if not problematic_rows.empty:
                    f.write(f"Found {len(problematic_rows)} rows with missing factor data\n")
                    f.write("First 5 problematic rows:\n")
                    f.write(problematic_rows.head().to_string())
                else:
                    f.write("No rows with missing factor data found\n")
        
        logger.info(f"Saved factor summary to {summary_file}")
        
    except Exception as e:
        logger.error(f"Failed to save debug information: {e}")

    logger.info(f"Calculated factors for {len(result)} symbols")
    return result


def _has_valid_values(series: pd.Series) -> bool:
    """Check if a series has valid (non-null, finite) values"""
    if series.empty:
        return False
    
    # Remove null values
    non_null = series.dropna()
    if non_null.empty:
        return False
    
    # Check for finite values (exclude inf, -inf)
    finite_values = non_null[np.isfinite(non_null)]
    if finite_values.empty:
        return False
    
    # Return True if we have at least some valid values (including zeros)
    # For financial factors, zero can be a meaningful value
    return len(finite_values) > 0


def _filter_valid_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out factor columns that don't have valid values"""
    if df.empty:
        return df
    
    columns_to_keep = []
    factor_columns_removed = []
    
    for col in df.columns:
        if isinstance(col, str) and col.endswith("因子"):
            if _has_valid_values(df[col]):
                columns_to_keep.append(col)
            else:
                factor_columns_removed.append(col)
                logger.info(f"Removing factor column '{col}' - no valid values")
        else:
            # Keep non-factor columns
            columns_to_keep.append(col)
    
    if factor_columns_removed:
        logger.info(f"Filtered out {len(factor_columns_removed)} invalid factor columns: {factor_columns_removed}")
    
    return df[columns_to_keep]


def _filter_symbols_without_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out symbols (rows) that have no valid factor values"""
    if df.empty:
        return df
    
    # Get all factor columns
    factor_columns = [col for col in df.columns if isinstance(col, str) and col.endswith("因子")]
    
    if not factor_columns:
        logger.warning("No factor columns found - returning all symbols")
        return df
    
    # Create a mask for rows that have at least one valid factor value
    valid_rows_mask = pd.Series([False] * len(df), index=df.index)
    
    for col in factor_columns:
        # For each factor column, check which rows have valid values (including zeros)
        col_valid = df[col].notna() & np.isfinite(df[col])
        valid_rows_mask = valid_rows_mask | col_valid
    
    # Filter the dataframe to only include rows with at least one valid factor
    filtered_df = df[valid_rows_mask].copy()
    
    symbols_removed = len(df) - len(filtered_df)
    if symbols_removed > 0:
        removed_symbols = df[~valid_rows_mask]['symbol'].tolist() if 'symbol' in df.columns else []
        logger.info(f"Filtered out {symbols_removed} symbols without valid factor values: {removed_symbols[:5]}{'...' if len(removed_symbols) > 5 else ''}")
    
    return filtered_df