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

