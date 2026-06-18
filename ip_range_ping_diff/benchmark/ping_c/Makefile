# Makefile for C ping benchmark
CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -pedantic
TARGET = ping_scan
SRC = ping_scan.c

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC)

clean:
	rm -f $(TARGET)
