import requests
import os
import openai

openai.api_key = os.environ.get('OPENAI_API_KEY')

def gather_user_input():
    print("Welcome to the Running Training Plan Generator!")
    
     # Ask for unit preference
    unit = input("Do you prefer kilometers (km) or miles (mi)? ").lower()
    while unit not in ["km", "mi"]:
        print("Invalid choice. Please select 'km' or 'mi'.")
        unit = input("Do you prefer kilometers (km) or miles (mi)? ").lower()

    # Adjust questions based on the chosen unit
    distance_question = f"How many {unit} do you currently run in a week? "
    longest_run_question = f"What's the longest distance you've run in the past month in {unit}? "

    # Collect user input
    fitness_level = int(input("On a scale of 1 to 10, with 1 being a beginner and 10 being an expert, how would you rate your current running fitness level? "))
    previous_races = input("Have you participated in any races before? If so, which distance and finish time did you complete your most recent race? ")
    weekly_distance = float(input(distance_question))
    longest_run = float(input(longest_run_question))
    training_days = int(input("How many days a week can you dedicate to running? "))
    past_injuries = input("Do you have any past injuries or limitations we should be aware of while designing your plan? ")
    distance_goal = input("What distance are you training for? (e.g., 5K, 10K, half marathon, marathon) ")
    time_goal = input("Do you have a specific time goal in mind for this distance? ")
    training_intensity = input("How intense would you like your training to be? (Easy, Moderate, Hard) ")
    start_date = input("When would you like to start your training? (YYYY-MM-DD) ")
    end_date = input("When is your race or the date by which you aim to achieve your goal? (YYYY-MM-DD) ")
    
    return {
        "fitness_level": fitness_level,
        "previous_races": previous_races,
        "weekly_mileage": weekly_distance,
        "longest_run": longest_run,
        "training_days": training_days,
        "past_injuries": past_injuries,
        "distance_goal": distance_goal,
        "time_goal": time_goal,
        "start_date": start_date,
        "end_date": end_date,
        "unit": unit
    }

def generate_training_plan_via_api(user_data):
    # Convert user data to a detailed prompt for ChatGPT
    prompt = f"""
    Generate a running training plan based on the following user details with blocks for building, strength and tapering.

    Please provide a plan from {user_data["start_date"]} to {user_data["end_date"]} based on the following details:
    Fitness Level: {user_data["fitness_level"]}
    Previous Races: {user_data["previous_races"]}
    Weekly Distance: {user_data["weekly_mileage"]} {user_data["unit"]}
    Longest Run: {user_data["longest_run"]} {user_data["unit"]}
    Training Days: {user_data["training_days"]}
    Past Injuries: {user_data["past_injuries"]}
    Distance Goal: {user_data["distance_goal"]}
    Time Goal: {user_data["time_goal"]}
    Start Date: {user_data["start_date"]}
    End Date: {user_data["end_date"]}
    
    Please specify the paces they should be run at.
    """

    system_msg = "You are an expert running coach"

    response = openai.ChatCompletion.create(
        model = "gpt-3.5-turbo",
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
            ],
        temperature = 0.2
        )

    # Extract the plan from the response
    # The exact extraction method might differ based on the API's response structure
    plan = response["choices"][0]["message"]["content"].strip()

    return plan

def save_to_file(training_plan):
    with open('./output/training_plan.txt', 'w') as file:
        file.write(training_plan)

def main():
    user_data = gather_user_input()
    training_plan = generate_training_plan_via_api(user_data)
    
    print("\nYour Training Plan:\n")
    print(training_plan)
    save_to_file(training_plan)

if __name__ == "__main__":
    main()