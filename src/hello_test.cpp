#include <gtest/gtest.h>
#include "hello.h"

TEST(HelloTest, ReturnsGreeting) {
  EXPECT_EQ(hello(), "Hello, world!");
}

TEST(HelloTest, ReturnsFloat) {
  EXPECT_FLOAT_EQ(hello_float(), 11.1f);
}

TEST(HelloTest, ReturnsNumber) {
  EXPECT_EQ(hello_number(), 123456);
}
