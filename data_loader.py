"""
Data Loader Module for Excel and CSV Files
Handles loading data from local Excel (.xlsx, .xls) and CSV files
Specifically designed for stock data with OHLCV (Open, High, Low, Close, Volume) format
"""

import pandas as pd
import os
from pathlib import Path
from typing import Optional, Dict, List, Union
import warnings


class ExcelDataLoader:
    """
    A class to load data from Excel files stored locally.
    Supports .xlsx and .xls file formats.
    """
    
    def __init__(self, data_directory: str = "data"):
        """
        Initialize the Excel Data Loader.
        
        Args:
            data_directory: Path to the directory containing Excel files (default: "data")
        """
        self.data_directory = Path(data_directory)
        self.data_directory.mkdir(exist_ok=True)
    
    def load_excel_file(
        self,
        filename: str,
        sheet_name: Optional[Union[str, int, List[Union[str, int]]]] = None,
        header: int = 0,
        skiprows: Optional[int] = None,
        usecols: Optional[Union[str, List[int]]] = None
    ) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """
        Load data from an Excel file.
        
        Args:
            filename: Name of the Excel file (with or without path)
            sheet_name: Name or index of sheet(s) to load. 
                       If None, loads first sheet.
                       If list, returns dict of DataFrames.
            header: Row to use as column names (default: 0)
            skiprows: Number of rows to skip at the start
            usecols: Columns to read (by index or name)
        
        Returns:
            DataFrame if single sheet, or Dict of DataFrames if multiple sheets
        
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file format is not supported
        """
        file_path = self.data_directory / filename
        
        # If file not in data directory, try as absolute/relative path
        if not file_path.exists():
            file_path = Path(filename)
            if not file_path.exists():
                raise FileNotFoundError(f"Excel file not found: {filename}")
        
        try:
            # Load Excel file
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                header=header,
                skiprows=skiprows,
                usecols=usecols,
                engine='openpyxl' if str(file_path).endswith('.xlsx') else 'xlrd'
            )
            
            return df
            
        except Exception as e:
            raise ValueError(f"Error loading Excel file {filename}: {str(e)}")
    
    def load_all_sheets(self, filename: str) -> Dict[str, pd.DataFrame]:
        """
        Load all sheets from an Excel file.
        
        Args:
            filename: Name of the Excel file
        
        Returns:
            Dictionary with sheet names as keys and DataFrames as values
        """
        return self.load_excel_file(filename, sheet_name=None)
    
    def list_excel_files(self) -> List[str]:
        """
        List all Excel files in the data directory.
        
        Returns:
            List of Excel file names
        """
        excel_files = []
        for ext in ['*.xlsx', '*.xls']:
            excel_files.extend(self.data_directory.glob(ext))
        
        return [f.name for f in excel_files]
    
    def list_data_files(self) -> List[str]:
        """
        List all data files (Excel and CSV) in the data directory.
        
        Returns:
            List of data file names
        """
        data_files = []
        for ext in ['*.xlsx', '*.xls', '*.csv']:
            data_files.extend(self.data_directory.glob(ext))
        
        return [f.name for f in data_files]
    
    def get_file_info(self, filename: str) -> Dict:
        """
        Get information about an Excel file (sheet names, dimensions, etc.)
        
        Args:
            filename: Name of the Excel file
        
        Returns:
            Dictionary with file information
        """
        file_path = self.data_directory / filename
        if not file_path.exists():
            file_path = Path(filename)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Excel file not found: {filename}")
        
        try:
            excel_file = pd.ExcelFile(file_path, engine='openpyxl' if str(file_path).endswith('.xlsx') else 'xlrd')
            
            info = {
                'filename': filename,
                'sheet_names': excel_file.sheet_names,
                'num_sheets': len(excel_file.sheet_names),
                'sheets_info': {}
            }
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name, nrows=0)
                info['sheets_info'][sheet_name] = {
                    'columns': list(df.columns),
                    'num_columns': len(df.columns)
                }
            
            return info
            
        except Exception as e:
            raise ValueError(f"Error reading file info for {filename}: {str(e)}")
    
    def load_csv_file(
        self,
        filename: str,
        header: int = 0,
        skiprows: Optional[int] = None,
        usecols: Optional[Union[str, List[int]]] = None
    ) -> pd.DataFrame:
        """
        Load data from a CSV file.
        
        Args:
            filename: Name of the CSV file (with or without path)
            header: Row to use as column names (default: 0)
            skiprows: Number of rows to skip at the start
            usecols: Columns to read (by index or name)
        
        Returns:
            DataFrame with the loaded data
        
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file format is not supported
        """
        file_path = Path(filename)
        
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {filename}")
        
        try:
            # Load CSV file
            df = pd.read_csv(
                file_path,
                header=header,
                skiprows=skiprows,
                usecols=usecols
            )
            
            return df
            
        except Exception as e:
            raise ValueError(f"Error loading CSV file {filename}: {str(e)}")
    
    def load_stock_data(
        self,
        filename: str,
        sheet_name: Optional[Union[str, int]] = None,
        date_column: Optional[str] = None,
        normalize_column_names: bool = True
    ) -> pd.DataFrame:
        """
        Load stock data from Excel or CSV file with required columns: date, open, high, low, close, volume.
        
        Args:
            filename: Name of the Excel or CSV file
            sheet_name: Name or index of sheet to load (default: first sheet, only for Excel)
            date_column: Name of the date column (auto-detected if None)
            normalize_column_names: If True, converts column names to lowercase and strips whitespace
        
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
            - Date column is converted to datetime
            - OHLCV columns are converted to numeric
            - Data is sorted by date
        
        Raises:
            ValueError: If required columns are missing
        """
        # Determine file type and load accordingly
        file_path = Path(filename)
        if not file_path.exists():
            # Try in data directory
            file_path = self.data_directory / filename
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {filename}")
        
        file_ext = file_path.suffix.lower()
        
        if file_ext == '.csv':
            # Load CSV file
            df = self.load_csv_file(str(file_path))
        elif file_ext in ['.xlsx', '.xls']:
            # Load Excel file
            df = self.load_excel_file(str(file_path), sheet_name=sheet_name)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}. Supported: .csv, .xlsx, .xls")
        
        # Normalize column names (lowercase, strip whitespace)
        if normalize_column_names:
            df.columns = df.columns.str.lower().str.strip()
        
        # Required stock data columns
        required_columns = {
            'date': ['date', 'datetime', 'time', 'timestamp', 'dt'],
            'open': ['open', 'o'],
            'high': ['high', 'h'],
            'low': ['low', 'l'],
            'close': ['close', 'c', 'closing'],
            'volume': ['volume', 'vol', 'v']
        }
        
        # Find matching columns (case-insensitive)
        column_mapping = {}
        available_columns = [str(col).lower().strip() for col in df.columns]
        
        for standard_name, possible_names in required_columns.items():
            found = False
            for col in df.columns:
                col_lower = str(col).lower().strip()
                if col_lower in possible_names or standard_name in col_lower:
                    column_mapping[standard_name] = col
                    found = True
                    break
            
            if not found:
                # Try exact match with normalized column
                if standard_name in available_columns:
                    idx = available_columns.index(standard_name)
                    column_mapping[standard_name] = df.columns[idx]
                    found = True
            
            if not found:
                raise ValueError(
                    f"Required column '{standard_name}' not found. "
                    f"Available columns: {list(df.columns)}. "
                    f"Looking for: {possible_names}"
                )
        
        # Select and rename columns
        stock_df = df[list(column_mapping.values())].copy()
        stock_df.columns = list(column_mapping.keys())
        
        # Convert date column to datetime
        stock_df['date'] = pd.to_datetime(stock_df['date'], errors='coerce')
        
        # Convert OHLCV columns to numeric
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            stock_df[col] = pd.to_numeric(stock_df[col], errors='coerce')
        
        # Remove rows with missing critical data
        initial_rows = len(stock_df)
        stock_df = stock_df.dropna(subset=['date', 'open', 'high', 'low', 'close'])
        if len(stock_df) < initial_rows:
            warnings.warn(
                f"Removed {initial_rows - len(stock_df)} rows with missing data",
                UserWarning
            )
        
        # Sort by date
        stock_df = stock_df.sort_values('date').reset_index(drop=True)
        
        # Reorder columns: date, open, high, low, close, volume
        stock_df = stock_df[['date', 'open', 'high', 'low', 'close', 'volume']]
        
        return stock_df
    
    def load_multiple_stocks(
        self,
        filenames: Optional[List[str]] = None,
        sheet_name: Optional[Union[str, int]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load stock data from multiple Excel files.
        
        Args:
            filenames: List of Excel file names. If None, loads all Excel files in data directory
            sheet_name: Name or index of sheet to load from each file (default: first sheet)
        
        Returns:
            Dictionary with stock symbols (from filenames) as keys and DataFrames as values
        """
        if filenames is None:
            filenames = self.list_excel_files()
        
        stocks_data = {}
        
        for filename in filenames:
            try:
                # Extract stock symbol from filename (remove extension)
                stock_symbol = Path(filename).stem
                stock_df = self.load_stock_data(filename, sheet_name=sheet_name)
                stocks_data[stock_symbol] = stock_df
            except Exception as e:
                warnings.warn(f"Failed to load {filename}: {str(e)}", UserWarning)
                continue
        
        return stocks_data


# Convenience functions for quick loading
def load_excel(filename: str, sheet_name: Optional[Union[str, int]] = None, data_dir: str = "data") -> pd.DataFrame:
    """
    Quick function to load a single sheet from an Excel file.
    
    Args:
        filename: Name of the Excel file
        sheet_name: Name or index of sheet to load (default: first sheet)
        data_dir: Directory containing Excel files (default: "data")
    
    Returns:
        DataFrame with the loaded data
    """
    loader = ExcelDataLoader(data_directory=data_dir)
    return loader.load_excel_file(filename, sheet_name=sheet_name)


def load_stock(filename: str, sheet_name: Optional[Union[str, int]] = None, data_dir: Optional[str] = None) -> pd.DataFrame:
    """
    Quick function to load stock data (OHLCV) from an Excel or CSV file.
    
    Args:
        filename: Name of the Excel or CSV file (can be full path or relative)
        sheet_name: Name or index of sheet to load (default: first sheet, only for Excel)
        data_dir: Directory containing data files (default: "data", ignored if filename is full path)
    
    Returns:
        DataFrame with columns: date, open, high, low, close, volume
    """
    # If filename is a full path, use it directly
    file_path = Path(filename)
    if file_path.is_absolute() or file_path.exists():
        loader = ExcelDataLoader(data_directory=".")  # Use current directory
        return loader.load_stock_data(filename, sheet_name=sheet_name)
    else:
        # Use data directory
        loader = ExcelDataLoader(data_directory=data_dir or "data")
        return loader.load_stock_data(filename, sheet_name=sheet_name)


if __name__ == "__main__":
    # Example usage
    loader = ExcelDataLoader()
    
    print("Excel Data Loader - Stock Data Example")
    print("=" * 50)
    
    # List available Excel files
    files = loader.list_excel_files()
    if files:
        print(f"\nAvailable Excel files: {files}")
        
        # Try to load as stock data
        print("\n" + "=" * 50)
        print("Loading Stock Data:")
        for file in files:
            try:
                stock_df = loader.load_stock_data(file)
                print(f"\n{file}:")
                print(f"  Shape: {stock_df.shape}")
                print(f"  Date range: {stock_df['date'].min()} to {stock_df['date'].max()}")
                print(f"  Columns: {list(stock_df.columns)}")
                print(f"\n  First few rows:")
                print(stock_df.head())
            except Exception as e:
                print(f"\n{file}: Error - {str(e)}")
                # Show file info instead
                try:
                    info = loader.get_file_info(file)
                    print(f"  Available columns: {info['sheets_info'][info['sheet_names'][0]]['columns']}")
                except:
                    pass
    else:
        print("\nNo Excel files found in 'data' directory.")
        print("Place your .xlsx or .xls files with stock data in the 'data' folder.")
        print("\nRequired columns: Date, Open, High, Low, Close, Volume")
        print("(Column names are case-insensitive and can have variations)")

