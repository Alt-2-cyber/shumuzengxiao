package com.shumuzengxiao.smartcattle;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class SmartCattleApplication {
    public static void main(String[] args) {
        SpringApplication.run(SmartCattleApplication.class, args);
    }
}
