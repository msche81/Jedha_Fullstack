import os
import zipfile
import tensorflow as tf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import mlflow
import mlflow.tensorflow
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, GlobalAveragePooling2D, Dense, Dropout, BatchNormalization, Input, Flatten
from tensorflow.keras.regularizers import l2
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

# --------------------
# 📌 Initialisation de MLflow
# --------------------
mlflow.set_tracking_uri("s3://skin-dataset-project")
mlflow.set_experiment("Skin_Type_Classification")
mlflow.tensorflow.autolog()

# 📌 URL publique du dataset sur S3
dataset_url = "https://skin-dataset-project.s3.amazonaws.com/oily-dry-and-normal-skin-types-dataset.zip"

# 📥 Téléchargement et extraction
with mlflow.start_run():
    dataset_path = tf.keras.utils.get_file(
        fname="oily-dry-and-normal-skin-types-dataset.zip",
        origin=dataset_url,
        extract=True
    )
    dataset_root = os.path.join(os.path.dirname(dataset_path), "Oily-Dry-Skin-Types")

    # 📌 Vérification que le dataset est bien téléchargé
    if not os.path.exists(dataset_root):
        raise FileNotFoundError(f"Dataset introuvable: {dataset_root}")

    # --------------------
    # 📌 Préparation des données
    # --------------------
    img_size = (224, 224)
    batch_size = 32

    train_datagen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=30,
        width_shift_range=0.2,
        height_shift_range=0.2,
        shear_range=0.2,
        zoom_range=0.2,
        horizontal_flip=True
    )

    valid_test_datagen = ImageDataGenerator(rescale=1./255)

    train_generator = train_datagen.flow_from_directory(
        os.path.join(dataset_root, "train"),
        target_size=img_size,
        batch_size=batch_size,
        class_mode="categorical"
    )

    valid_generator = valid_test_datagen.flow_from_directory(
        os.path.join(dataset_root, "valid"),
        target_size=img_size,
        batch_size=batch_size,
        class_mode="categorical"
    )

    test_generator = valid_test_datagen.flow_from_directory(
        os.path.join(dataset_root, "test"),
        target_size=img_size,
        batch_size=batch_size,
        class_mode="categorical"
    )

    # --------------------
    # 📌 Construction du modèle CNN
    # --------------------
    model = Sequential([
        Input(shape=(224, 224, 3)),
        Conv2D(32, (3,3), activation='relu', padding="same"),
        BatchNormalization(),
        MaxPooling2D(pool_size=(2,2)),

        Conv2D(64, (3,3), activation='relu', padding="same"),
        BatchNormalization(),
        MaxPooling2D(pool_size=(2,2)),

        Conv2D(128, (3,3), activation='relu', padding="same"),
        BatchNormalization(),
        MaxPooling2D(pool_size=(2,2)),

        Conv2D(256, (3,3), activation='relu'),
        BatchNormalization(),
        MaxPooling2D(pool_size=(2,2)),

        Flatten(),
        Dense(64, activation='relu', kernel_regularizer=l2(0.005)),
        Dropout(0.5),
        Dense(32, activation='relu', kernel_regularizer=l2(0.005)),
        Dropout(0.3),
        Dense(3, activation='softmax')
    ])

    # 📌 Compilation du modèle
    learning_rate = 0.001
    model.compile(
        optimizer=Adam(learning_rate=learning_rate),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )

    # 📌 Affichage du résumé du modèle
    model.summary()

    # --------------------
    # 📌 Entraînement du modèle
    # --------------------
    num_epochs = 20
    early_stopping = EarlyStopping(
        monitor="val_loss", patience=2, restore_best_weights=True, verbose=1
    )

    reduce_lr = ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=2,
        min_lr=1e-6
    )

    history = model.fit(
        train_generator,
        epochs=num_epochs,
        validation_data=valid_generator,
        callbacks=[early_stopping, reduce_lr],
        verbose=1
    )

    # --------------------
    # 📌 Logging des métriques et enregistrement du modèle
    # --------------------
    mlflow.log_param("learning_rate", learning_rate)
    mlflow.log_param("epochs", num_epochs)
    mlflow.log_param("train_size", train_generator.samples)
    mlflow.log_param("valid_size", valid_generator.samples)  # Ajout ici ✅

    mlflow.log_metric("final_train_accuracy", history.history['accuracy'][-1])
    mlflow.log_metric("final_val_accuracy", history.history['val_accuracy'][-1])

    # 📌 Sauvegarde du modèle au format recommandé
    model.save("cnn_skin_classifier.keras", save_format="keras")  # Ajout ici ✅

    # 📌 Enregistrement du modèle dans MLflow
    mlflow.tensorflow.log_model(model, "cnn_skin_classifier")