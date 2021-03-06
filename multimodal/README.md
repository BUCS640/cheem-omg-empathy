
# Multimodal models for the OMG Empathy Challenge

This is a guide to training and cross-validating our multi-modal feature-level fusion models. An interactive Jupyter Notebook version can be found at README.ipynb.

#### Table of Contents
- Training feature-level fusion models
- Cross-validation across stories
- Cross-validation across epochs
- Fine-tuning personalized models
- Decision-level (DL) fusion
- Cross-validation for DL fusion

## Training feature-level fusion models

Our best-performing feature-level fusion models were the **audio+text (AT) model** (best on story 1 as validation) and the **audio+text+visual (ATV) model** (best on cross-validation), where we only used the subject visual features.

Assuming the training and validation data is stored in `./data/Training/` and `./data/Validation/` respectively, the following commands will train the AT and ATV models for 2000 epochs.


```shell
python train.py --cuda --epochs 2000 --mods audio,text --model_dir models_AT
```


```shell
python train.py --cuda --epochs 2000 --mods audio,text,v_sub --model_dir models_ATV
```

To save predictions and evaluate against the validation set, run:


```shell
python train.py --cuda --mods audio,text --model_dir models_AT --pred_dir preds_AT --test
```


```shell
python train.py --cuda --mods audio,text,v_sub --model_dir models_ATV --pred_dir preds_ATV --test
```

To predict on the test set, make sure there are dummy valence annotations of the correct length (i.e. number of frames) in the folder `./data/Testing/Annotations`. Then run:


```shell
python train.py --cuda --mods audio,text --model_dir models_AT --test --test_dir ./data/Testing
```


```shell
python train.py --cuda --mods audio,text,v_sub --model_dir models_ATV --test --test_dir ./data/Testing
```

The predictions on the test set will be stored in `./pred_test`.

## Cross-validation across stories

To evaluate how well these models perform when cross-validated across stories, we can run the following scripts. **This will take some time** because the model is trained 5 times (5 different validation sets) for 2000 epochs.


```shell
python crossval.py --cuda --epochs 2000 --mods audio,text --out_dir cv_AT --save_freq 10
```


```shell
python crossval.py --cuda --epochs 2000 --mods audio,text,v_sub --out_dir cv_ATV --save_freq 10
```

Results will be saved in `cv_AT/crossval.csv` and `cv_ATV/crossval.csv` respectively.

By default, the scripts above will save and report the results for the best epoch on each validation set (i.e. early stopping). To report the results for a constant epoch number across validation sets, we can set the `test_epoch` flag. Note that the model files for the test epoch must have already been saved.


```shell
python crossval.py --cuda --mods audio,text --out_dir cv_AT --test --test_epoch 1360
```


```shell
python crossval.py --cuda --mods audio,text,v_sub --out_dir cv_ATV --test --test_epoch 1900
```

## Cross-validation across epochs
To find out which is best epoch when cross-validated across all stories, we can run the following (make sure that the directories specified by the `out_dir` flag were already generated by the previous script).


```shell
python cv_epochs.py --cuda --mods audio,text --out_dir cv_AT
```


```shell
python cv_epochs.py --cuda --mods audio,text,v_sub --out_dir cv_ATV
```

## Fine-tuning personalized models

We first copy the models we would like to fine-tune into new folders:


```shell
mkdir personal_AT personal_ATV
```


```shell
cp cv_AT/val_on_1/best.save personal_AT/init.save
```


```shell
cp cv_ATV/val_on_1/epoch_1900.save personal_ATV/init.save
```

Now we can run the following scripts to fine-tune the models for each subject for 250 epochs:


```shell
python personalize.py --cuda --mods audio,text --out_dir personal_AT --epochs 250
```


```shell
python personalize.py --cuda --mods audio,text,v_sub --out_dir personal_ATV --epochs 250
```

The corresponding predictions will be stored in `personal_AT/pred_test` and `personal_ATV/pred_test`.

## Decision-level (DL) fusion

Decision-level fusion using Support Vector Regression (SVR) can be performed by first extracting the decision-level features from the final fully-connected layer of each pre-trained model. For illustration, we will do decision level fusion between the AT and ATV models trained above. We extract the features by running:


```shell
python train.py --cuda --mods audio,text --model_dir models_AT --feat_dir feat_AT --features
```


```shell
python train.py --cuda --mods audio,text,v_sub --model_dir models_ATV --feat_dir feat_ATV --features
```

The features will now be stored in `./feat_AT` and `./feat_ATV` respectively. We then copy these features into `./data/Training` and `./data/Validation`:


```shell
cp feat_AT/feat_train data/Training/feat_AT && cp feat_AT/feat_test data/Validation/feat_AT
```


```shell
cp feat_ATV/feat_train data/Training/feat_ATV && cp feat_ATV/feat_test data/Validation/feat_ATV
```

Now we can call `fusion.py` to fit the features to an SVR model:


```shell
python fusion.py feat_AT feat_ATV --normalize
```

The predictions will be stored in `./fusion_preds`.

## Cross-validation for DL fusion

To run cross-validation for DL fusion, we first need to make sure cross-validation has been run for each of the models that is being fused. Since we've already done this for the AT and ATV models, all we need to do is run the following script.


```shell
python cv_fusion.py cv_AT cv_ATV --normalize --in_names AT ATV
```

The results and models will be saved in `./cv_fusion_out`.
