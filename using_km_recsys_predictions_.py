# -*- coding: utf-8 -*-
"""Using_KM_RecSys_Predictions.

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1CuqREXyz1x7n9AfusdGgSqlJ-Pw6sf4J
"""

from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel
from pyspark.sql.functions import col, expr, radians, lit, row_number, sqrt, sin, cos, asin,power
from pyspark.sql.window import Window
from pyspark.ml.feature import StringIndexer, VectorAssembler, StandardScaler

class RestaurantRecommenderPredictor:
    def __init__(self, spark_session):
        """
        Initialize the Restaurant Recommender Predictor
        """
        self.spark = spark_session
        self.df = None
        self.kmeans_model = None
        self.cuisine_indexer = None
        self.vector_assembler = None
        self.scaler = None

    def load_data(self, data_path):
        """
        Load and preprocess restaurant data
        """
        # Read the CSV file
        self.df = self.spark.read.csv(data_path, header=True, inferSchema=True)

        # Data cleaning and preprocessing
        self.df = self.df.na.drop()  # Remove rows with null values

        # Convert boolean columns
        self.df = (self.df.withColumn("has_parking",
                    expr("CASE WHEN parking = 'Yes' THEN true ELSE false END"))
                   .withColumn("has_wifi",
                    expr("CASE WHEN WiFi = 'Yes' THEN true ELSE false END")))

        # Encode categorical variables
        self.cuisine_indexer = StringIndexer(
            inputCol="cuisine_type",
            outputCol="cuisine_type_encoded"
        )
        self.df = self.cuisine_indexer.fit(self.df).transform(self.df)

        return self.df

    def load_saved_model(self, model_path):
        """
        Load the saved PySpark Pipeline Model
        """
        try:
            # Load the entire pipeline model
            self.kmeans_model = PipelineModel.load(model_path)

            # Extract specific stages from the pipeline
            stages = self.kmeans_model.stages

            # Find and store vector assembler and scaler
            for stage in stages:
                if isinstance(stage, VectorAssembler):
                    self.vector_assembler = stage
                elif isinstance(stage, StandardScaler):
                    self.scaler = stage

            return self.kmeans_model
        except Exception as e:
            print(f"Error loading model: {e}")
            return None

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate distance between two geographical points
        """
        lat1_rad = radians(lit(lat1))
        lon1_rad = radians(lit(lon1))
        lat2_rad = radians(lat2)
        lon2_rad = radians(lon2)

        return (
            6371 * 2 * asin(
                sqrt(
                    sin((lat2_rad - lat1_rad) / 2) ** 2 +
                    cos(lat1_rad) * cos(lat2_rad) *
                    sin((lon2_rad - lon1_rad) / 2) ** 2
                )
            )
        )

    def recommend_restaurants(
        self,
        user_location,
        min_rating,
        need_parking,
        need_wifi,
        cuisine_type,
        max_distance=60
    ):
        """
        Recommend restaurants based on user preferences
        """
        user_lat, user_lon = user_location

        # Apply initial filters
        filtered_df = self.df.filter(
            (col("rating") >= min_rating) &
            (col("cuisine_type") == cuisine_type)
        )

        # Apply parking filter
        if need_parking:
            filtered_df = filtered_df.filter(col("has_parking") == True)

        # Apply WiFi filter
        if need_wifi:
            filtered_df = filtered_df.filter(col("has_wifi") == True)

        # Add distance column
        with_distance_df = filtered_df.withColumn(
            "distance",
            self.haversine_distance(user_lat, user_lon, col("latitude"), col("longitude"))
        )

        # Filter by distance
        nearby_restaurants = with_distance_df.filter(
            col("distance") <= max_distance
        )

        # Rank restaurants
        window_spec = Window.partitionBy("bus_name").orderBy(col("rating").desc())

        recommended_restaurants = (
            nearby_restaurants
            .withColumn("rank", row_number().over(window_spec))
            .filter(col("rank") == 1)
            .orderBy(col("rating").desc())
            .select("business_id", "bus_name", "address", "rating", "distance", "cuisine_type")
            .limit(5)
        )

        return recommended_restaurants

def interactive_recommendation(predictor):
    """
    Interactive restaurant recommendation interface
    """
    print("Restaurant Recommender System")

    # Get user inputs
    user_lat = float(input("Enter your latitude: "))
    user_lon = float(input("Enter your longitude: "))
    min_rating = float(input("Enter minimum rating (0-5): "))
    need_parking = input("Need parking? (yes/no): ").lower() == 'yes'
    need_wifi = input("Need WiFi? (yes/no): ").lower() == 'yes'
    cuisine_type = input("Enter cuisine type: ")

    # Make recommendations
    recommendations = predictor.recommend_restaurants(
        user_location=(user_lat, user_lon),
        min_rating=min_rating,
        need_parking=need_parking,
        need_wifi=need_wifi,
        cuisine_type=cuisine_type
    )

    # Show recommendations
    recommendations.show()

def main():
    # Create Spark Session
    spark = SparkSession.builder \
        .appName("RestaurantRecommenderPredictor") \
        .getOrCreate()

    # Define paths
    model_path = '/content/drive/MyDrive/Models/restaurant_recommender_Final_model'
    data_path = '/content/drive/MyDrive/ProcessedCSV/Recommender_System_Newdata.csv'

    try:
        # Initialize predictor
        predictor = RestaurantRecommenderPredictor(spark)

        # Load dataset
        predictor.load_data(data_path)

        # Load saved model
        loaded_model = predictor.load_saved_model(model_path)

        if loaded_model:
            # Start interactive recommendation
            interactive_recommendation(predictor)
        else:
            print("Failed to load the model.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        spark.stop()

if __name__ == "__main__":
    main()