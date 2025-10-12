import json
import polars as pl
import re
from typing import List, Dict, Any, Optional


def sample_majority_vote(
    df: pl.DataFrame,
    group_by_cols: List[str],
    n_samples: Optional[int] = None,
    resolve_group: Optional[str] = None
) -> pl.DataFrame:
    """
    Groups a DataFrame and returns the most frequently occurring value for each column
    within each group. If a group has more rows than n_samples, and resolve_group is provided,
    further splits those groups by resolve_group and applies the majority vote within these subgroups.

    Args:
        df: The input Polars DataFrame.
        group_by_cols: A list of column names to group the DataFrame by.
        n_samples: The expected number of samples per group (for ambiguity detection).
        resolve_group: An optional column name to further group ambiguous groups.

    Returns:
        A new DataFrame with one row per group, showing the majority-voted value
        for each column. Ambiguous groups are split by resolve_group if provided.
    """
    if n_samples is None:
        # infer n_samples from the data if not provided
        n_samples = df["sample"].n_unique() if "sample" in df.columns else 1

    # Identify the columns to apply the majority vote to
    majority_vote_cols = [col for col in df.columns if col not in group_by_cols and col != "sample"]

    # Helper to build grouped aggregation expressions
    def build_aggs(cols):
        aggs = []
        for col in cols:
            # Calculate the mode and its proportion
            mode_info = pl.col(col).value_counts(sort=True, normalize=True).first()
            aggs.append(mode_info.struct.field(col).alias(col))
            aggs.append(mode_info.struct.field("proportion").alias(f"{col}_agreement"))
        return aggs

    # Group by initial group_by_cols to find group sizes
    grouped = df.group_by(group_by_cols, maintain_order=True).agg([pl.len().alias("_group_size")])
    
    # Find ambiguous groups (= group contains more than n_samples rows)
    ambiguous_keys = grouped.filter(pl.col("_group_size") > n_samples).select(group_by_cols)
    
    # Split df into ambiguous and unambiguous
    df_unambiguous = df.join(ambiguous_keys, on=group_by_cols, how="anti")
    df_ambiguous = df.join(ambiguous_keys, on=group_by_cols, how="semi")

    result = []
    # Majority vote for unambiguous groups
    if len(df_unambiguous) > 0:
        aggs = build_aggs(majority_vote_cols)
        res_unamb = (
            df_unambiguous.group_by(group_by_cols)
            .agg(aggs + [pl.len().alias("n_samples")])
            .sort(group_by_cols)
        )
        res_unamb = res_unamb.with_columns(pl.lit(False).alias("ambiguous"))
        result.append(res_unamb)

    # For ambiguous groups, fallback to resolve_group if provided
    if len(df_ambiguous) > 0 and resolve_group is not None:
        group_cols = group_by_cols + [resolve_group]
        ambiguous_majority_cols = [col for col in majority_vote_cols if col != resolve_group]
        aggs = build_aggs(ambiguous_majority_cols)
        res_amb = (
            df_ambiguous.group_by(group_cols)
            .agg(aggs + [pl.len().alias("n_samples")])
            .sort(group_cols)
        )
        res_amb = res_amb.with_columns(pl.lit(True).alias("ambiguous"))
        result.append(res_amb)
    elif len(df_ambiguous) > 0:
        # If no resolve_group, just aggregate as usual
        aggs = build_aggs(majority_vote_cols)
        res_amb = (
            df_ambiguous.group_by(group_by_cols)
            .agg(aggs + [pl.len().alias("n_samples")])
            .sort(group_by_cols)
        )
        res_amb = res_amb.with_columns(pl.lit(True).alias("ambiguous"))
        result.append(res_amb)

    # Concatenate results
    if result:
        return pl.concat(result, how='diagonal_relaxed').rechunk()
    else:
        return pl.DataFrame()
    


def parse_markdown_table(md_text: str) -> pl.DataFrame:
    """
    Parse a markdown table from a string into a Polars DataFrame.
    Expects first row to be header, second row to be separator.
    Only lines starting with '|' are considered table rows.
    """
    # Filter lines that look like markdown table rows
    table_lines = [line.strip() for line in md_text.splitlines() if line.strip().startswith('|')]
    if not table_lines:
        raise ValueError("No markdown table found in input text.")
    # Remove separator row (e.g. |---|---|)
    header = table_lines[0]
    sep_idx = 1 if len(table_lines) > 1 and re.match(r"\|[\-\s\|]+\|", table_lines[1]) else None
    if sep_idx:
        rows = [header] + table_lines[2:]
    else:
        rows = table_lines
    # Split each row into columns
    split_rows = [re.split(r'\s*\|\s*', row.strip('| ')) for row in rows]
    # First row is header
    columns = split_rows[0]
    data_rows = split_rows[1:]
    return pl.DataFrame(data_rows, schema=columns)
