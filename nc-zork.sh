#!/bin/bash

PORT=2323  # Change this to the desired port
PROGRAM_PATH="/opt/zork/mojozork"  # Change this to the actual path of your program
MAX_CONNECTIONS=2

fifo_cleanup() {
  # Clean up all named pipes when script is terminated
  rm -f /tmp/nc_fifo_*
}

trap fifo_cleanup EXIT

while true; do
  # Generate a unique named pipe for the current client connection
  PIPE="/tmp/nc_fifo_$$"
  mkfifo "$PIPE"

  # Use a counter to keep track of active connections
  active_connections=0

  # Loop until maximum connections are reached
  while [ "$active_connections" -lt "$MAX_CONNECTIONS" ]; do
    # Accept incoming connection and spawn a new instance of the program
    {
      # Generate a unique named pipe for the program output
      OUTPUT_PIPE="/tmp/output_fifo_$$"
      mkfifo "$OUTPUT_PIPE"

      # Run the program with the input from the client and output to the unique output pipe
      "$PROGRAM_PATH" < "$PIPE" > "$OUTPUT_PIPE" &

      # Read from the unique output pipe and send it back to the client using nc in the background
      nc -l -p "$PORT" < "$OUTPUT_PIPE" &
      
      # Clean up the unique output pipe
      rm "$OUTPUT_PIPE"
    } &
    
    # Increment the counter and sleep for a short duration
    active_connections=$((active_connections + 1))
    sleep 0.1
  done

  # Wait for all active connections to complete before proceeding
  wait

  # Clean up the named pipe after the connections are closed
  rm "$PIPE"
done

