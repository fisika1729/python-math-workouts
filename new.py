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
    
    # Prepare columns
    columns = [[] for _ in range(num_columns)]  # Store columns' numbers
    idx = 0

    # Generate the sequence
    for num in sequence:
        for col in range(num_columns):
            columns[col].append(num)  # Add number to each column

        # Clear the screen and redraw
        stdscr.clear()

        # Print falling numbers in each column
        for col in range(num_columns):
            col_width = width // num_columns
            for row in range(len(columns[col])):
                # Position the numbers to fall down
                stdscr.addstr(row, col * col_width + 2, str(columns[col][row]))

        stdscr.refresh()  # Update the screen
        time.sleep(delay)  # Add delay to create the falling effect

        # Simulate fading (clear the first row and move others up)
        for col in range(num_columns):
            if len(columns[col]) > 1:
                columns[col] = columns[col][1:]  # Remove the first item (fade effect)

        # Limit the length of the sequence and fade effect
        if idx >= len(sequence) - 1:
            break
        idx += 1

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
