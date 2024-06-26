from os.path import join
from typing import Optional
import torch
from torch.utils.data import Dataset
import pandas as pd
import lightning as L
from torch.utils.data import random_split, DataLoader


from src.utils.data import download_data, column_transformer, setup_dataframes
from src.transforms import ToTensor


class HousePricingDataset(Dataset):
    """House Pricing dataset."""

    def __init__(
        self,
        df: pd.DataFrame,
        predict: bool = False,
        target_column_name="SalePrice",
        id_column_name="Id",
        transform=None,
    ):
        """
        Arguments:
            df (pd.DataFrame): dataframe to use as dataset.
            predict (bool): either to train or to make predictions
            transform (callable, optional): Optional transform to be applied
                on a sample.
        """

        self.labels = None
        self.ids = None

        self.predict = predict
        self.transform = transform

        self.samples = df.drop(
            [id_column_name, target_column_name], axis=1, errors="ignore"
        )
        self.ids = df[id_column_name]
        self.labels = None

        if not self.predict:
            self.labels = df["SalePrice"]

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()

        X = self.samples.iloc[idx]
        X = X.to_numpy()

        ids = self.ids[idx]

        if not self.predict:
            y = self.labels.iloc[idx]

        batch = (
            {"id": ids, "inputs": X, "target": y}
            if not self.predict
            else {"id": ids, "inputs": X}
        )

        if self.transform:
            batch = self.transform(batch)

        return batch


class HousePricingDataModule(L.LightningDataModule):
    def __init__(
        self,
        data_dir: Optional[str] = None,
        batch_size: int = 32,
        eval_batch_size=128,
        validation_size=0.0
    ):

        super().__init__()

        self.validation = True
        self.test = True
        self.predict = True

        self.validation_size = validation_size
        self.test_size = 0.1

        if self.validation_size <= 0:
            self.validation = False

        self.batch_size = batch_size
        self.eval_batch_size = eval_batch_size

        self.data_dir = data_dir if data_dir else join("data")

        self.fit_df = None
        self.test_df = None
        self.predict_df = None

        self.train_dataset = None
        self.validation_dataset = None
        self.test_dataset = None
        self.predict_dataset = None

        self.column_transformer = column_transformer()

    def prepare_data(self) -> None:
        download_data("download_data.sh")
        self._setup_dataframes()

    def _setup_dataframes(self):
        dataframes = setup_dataframes(
            self.data_dir,
            self.column_transformer,
            test_size=self.test_size,
        )

        self.fit_df = dataframes["fit"]
        self.test_df = dataframes["test"]
        self.predict_df = dataframes["predict"]

    def setup(self, stage: str):
        print(f"[INFO]: Setting up {stage} dataset/s")
        if stage == "fit":
            self._setup_fit_datasets()
        if stage == "test":
            self._setup_test_dataset()
        if stage == "predict":
            self._setup_predict_dataset()

    def _setup_fit_datasets(self) -> None:
        train_dataset = HousePricingDataset(self.fit_df, transform=ToTensor())
        if self.validation:
            self.train_dataset, self.validation_dataset = random_split(
                train_dataset,
                [1 - self.validation_size, self.validation_size],
                generator=torch.Generator().manual_seed(42),
            )
            print(f"[INFO]: Train dataset size: {len(self.train_dataset)}")
            print(f"[INFO]: Validation dataset size: {len(self.validation_dataset)}")
        else:
            self.train_dataset = train_dataset
            print(f"[INFO]: Train dataset size: {len(self.train_dataset)}")

    def _setup_test_dataset(self) -> None:
        self.test_dataset = HousePricingDataset(self.test_df, transform=ToTensor())

    def _setup_predict_dataset(self) -> None:
        self.predict_dataset = HousePricingDataset(
            self.predict_df, predict=True, transform=ToTensor()
        )

    def train_dataloader(self):
        if not self.train_dataset:
            raise Exception("[ERROR]: fit stage not set up")
        # return DataLoader(self.housing_train, batch_size=self.batch_size, num_workers=optim_workers())
        dl = DataLoader(self.train_dataset, batch_size=self.batch_size, shuffle=True)
        print(f"[INFO]: Train dataloader size: {len(dl)}")
        return dl

    def val_dataloader(self):
        if not self.validation_dataset:
            raise Exception("[ERROR]: fit stage not set up")
        # return DataLoader(self.housing_val, batch_size=self.batch_size, num_workers=optim_workers())
        dl = DataLoader(
            self.validation_dataset, batch_size=self.eval_batch_size, shuffle=True
        )
        print(f"[INFO]: Validation dataloader size: {len(dl)}")
        return dl

    def test_dataloader(self):
        if not self.test_dataset:
            raise Exception("[ERROR]: test stage not set up")
        # return DataLoader(self.housing_test, batch_size=self.batch_size, num_workers=optim_workers())
        dl = DataLoader(self.test_dataset, batch_size=self.eval_batch_size)
        print(f"[INFO]: Test dataloader size: {len(dl)}")
        return dl

    def predict_dataloader(self):
        if not self.predict_dataset:
            raise Exception("[ERROR]: predict stage not set up")
        # return DataLoader(self.housing_predict, batch_size=self.batch_size, num_workers=optim_workers())
        dl = DataLoader(self.predict_dataset, batch_size=self.eval_batch_size)
        print(f"[INFO]: Predict dataloader size: {len(dl)}")
        return dl

    def data_features(self) -> int:
        """Returns the number of features given by the data.
        We substract 2 features because we don't take in account
        the sample price and the sample id
        """
        return self.fit_df.shape[1] - 2
