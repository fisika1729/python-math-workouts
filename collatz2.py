import curses
import random
import time

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

# Function to display the Matrix-style falling effect
def display_falling_matrix(stdscr, sequence, num_columns=5, delay=0.1):
    curses.curs_set(0)  # Hide cursor
    height, width = stdscr.getmaxyx()  # Get screen dimensions
    stdscr.nodelay(1)  # Don't block for user input

    # Create a list of columns to hold numbers
    columns = [[] for _ in range(num_columns)]
    # Create an index tracker for each column
    idxs = [0] * num_columns
    num_falls = len(sequence)  # Max number of falls
    
    while True:
        stdscr.clear()

        # Populate the columns with falling numbers
        for col in range(num_columns):
            col_width = width // num_columns
            if idxs[col] < num_falls:
                num_to_display = sequence[idxs[col]]
                # Display each number in its column
                stdscr.addstr(idxs[col] % height, col * col_width + 2, str(num_to_display))

                # Move to the next number in the sequence for that column
                idxs[col] += 1

        # Simulate the fading effect (numbers disappear as they reach the bottom)
        for col in range(num_columns):
            if idxs[col] >= num_falls:
                idxs[col] = 0  # Reset the column index to start the falling effect again

        # Refresh the screen to display changes
        stdscr.refresh()
        time.sleep(delay)

        # Check if we need to exit or keep looping
        if all(idx >= num_falls for idx in idxs):
            break

# Main function to run the effect
def main(stdscr):
    # Pick a large random number between 100 and 999
    start_num = random_number(100, 999)
    print(f"Starting Collatz sequence with: {start_num}")
    
    # Generate the Collatz sequence
    sequence = collatz_sequence(start_num)
    
    # Display the falling matrix effect
    display_falling_matrix(stdscr, sequence)

# Run the curses application
if __name__ == "__main__":
    curses.wrapper(main)
