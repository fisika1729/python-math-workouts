# def collatz_sequence(n):
#     """
#     Generates the Collatz sequence for a given positive integer n.
#     Args:
#         n: A positive integer to start the sequence.
#     Returns:
#         A list containing the Collatz sequence from n down to 1.
#     """
#     if n <= 0:
#         raise ValueError("Input must be a positive integer.")

#     sequence = [n]
#     while n != 1:
#         if n % 2 == 0:  # n is even
#             n = n // 2
#         else:  # n is odd
#             n = 3 * n + 1
#         sequence.append(n)
#     return sequence

# # Example usage:
# starting_number = int(input("Enter a positive integer: "))
# try:
#     result_sequence = collatz_sequence(starting_number)
#     print(f"Collatz sequence for {starting_number}: {result_sequence}")
# except ValueError as e:
#     print(f"Error: {e}")

import random
import time
import os

# Function to generate a random number
def random_number(min_val, max_val):
    return random.randint(min_val, max_val)

# Function to generate Collatz sequence
def collatz_sequence(n):
    sequence = [n]
    while n != 1:
        if n % 2 == 0:
            n //= 2
        else:
            n = 3 * n + 1
        sequence.append(n)
    return sequence

# Function to display the falling matrix effect
def display_falling_matrix(sequence, delay=0.1):
    # Get terminal width and height to size the output
    width = os.get_terminal_size().columns
    height = os.get_terminal_size().lines

    for num in sequence:
        # Create the "falling" effect by printing the number falling down
        os.system('cls' if os.name == 'nt' else 'clear')  # Clear screen for each new frame
        num_str = str(num)
        # Display the numbers in the center and let them fall
        for i in range(height - 1):
            spaces = ' ' * (width // 2 - len(num_str) // 2)
            print(spaces + num_str)
            time.sleep(delay)
        # After displaying one, we display the next number in the sequence
        print("\n\n")
        time.sleep(delay)

# Main function
def main():
    # Pick a large random number between 100 and 999
    start_num = random_number(100000000, 999999999)
    print(f"Starting Collatz sequence with: {start_num}")
    
    # Generate the Collatz sequence
    sequence = collatz_sequence(start_num)
    
    # Display the sequence with the falling matrix effect
    display_falling_matrix(sequence)

if __name__ == "__main__":
    main()
