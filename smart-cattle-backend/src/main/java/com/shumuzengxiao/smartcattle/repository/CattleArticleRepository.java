package com.shumuzengxiao.smartcattle.repository;

import com.shumuzengxiao.smartcattle.domain.CattleArticle;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface CattleArticleRepository extends JpaRepository<CattleArticle, String> {
    List<CattleArticle> findTop150ByOrderByPublishedAtDescIdAsc();
    List<CattleArticle> findByKindOrderByIdAsc(String kind);
}
