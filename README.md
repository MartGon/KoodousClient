# DroidRisk (Malware Classifier)

## Description

 DroidRisk is an Android malware classification tool. Its approach is purely based on static analysis with the objective of achieving early detection of malware. In order to do this, we had to train four different AI models, each of them with static features of a particular category, such as Android permissions or the strings found within the app. After ensuring the validity of the results employing 10 Fold cross validation, the program scores 98% accuracy by combining the results of the four models.

 ## Dataset

**IMPORTANT**: The dataset used for training is not publicly available.

Despite the fact that it wasn't necessary, I decided to assemble my own dataset of samples, which was made of around 800 applications, half of them being malware. I found my malware samples using the webpage [Koodous](https://koodous.com), which is a collaborative platform were applications are uploaded at a daily basis and they are classified by many malware analysts. The so called goodware samples were obtained from Google Play.

## Architecture

This project is divided in several modules. The most important ones are:

- **ClassifierServer.py**: This is the main application. Loads the already trained model and hosts a server on a specific port. The server will respond to APK verification requests with a percent corresponding to how likely the provided file is a malware sample.

- **DatasetRetriever.py**: Helper program which can be used to download samples. Malware samples are downloaded from [Koodous](https://koodous.com), whereas goodware are downloaded from Google Play. In order to download malware samples, you'll need get an API token from Koodous, which can be obtained by creating a free account on the site. After a sample is download, static features are extracted.

- **DatasetStatistics.py**: Plots an histogram with the most common features in the dataset by feature category, either permissions or functionality.

- **DatasetTrainer.py**: Trains the AI model with the provided dataset database file. Some training params can be provided, such as: category of features to be used, amount of features to employ, cross validation iterations, etc. This program generates the AI model file which will be loaded the **ClassifierServer.py**.

Most, if not all, of these programs take a path to a SQLite3 database file as param, where the dataset relevant information is stored. You can use the **DatasetRetriever.py** to extract the static features and update the database information. 

## Usage

In order to make this project accesible to most people, I made an [Android application](https://github.com/MartGon/DroidRiskClient) which works as a client to the **ClassiferServer.py** module.

## About

This work is what I presented as my Cybersecurity master project. You can read it [here](https://drive.google.com/file/d/1Va6FYQ6zSTOTYzp0lN0L7SGSyP9bPrD6/view?usp=sharing)