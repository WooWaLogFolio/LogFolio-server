package com.woowa.logfolio.file;

import com.woowa.logfolio.ai.AiServerContract;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.poi.hslf.usermodel.HSLFSlideShow;
import org.apache.poi.xslf.usermodel.XMLSlideShow;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.hwpf.HWPFDocument;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

@Service
public class DocumentTextExtractor {

    public List<AiServerContract.Page> extract(Path source, String originalName) {
        String extension = extension(originalName);
        try {
            return switch (extension) {
                case "pdf" -> extractPdf(source);
                case "pptx" -> extractPptx(source);
                case "ppt" -> extractPpt(source);
                case "docx" -> extractDocx(source);
                case "doc" -> extractDoc(source);
                default -> throw new IllegalArgumentException("AI 텍스트 추출을 지원하지 않는 파일 형식입니다: " + extension);
            };
        } catch (IOException exception) {
            throw new IllegalStateException("파일 텍스트 추출에 실패했습니다.", exception);
        }
    }

    private List<AiServerContract.Page> extractPdf(Path source) throws IOException {
        try (PDDocument document = Loader.loadPDF(source.toFile())) {
            PDFTextStripper stripper = new PDFTextStripper();
            List<AiServerContract.Page> pages = new ArrayList<>();
            for (int page = 1; page <= document.getNumberOfPages(); page++) {
                stripper.setStartPage(page);
                stripper.setEndPage(page);
                addPage(pages, page, stripper.getText(document));
            }
            return requireText(pages);
        }
    }

    private List<AiServerContract.Page> extractPptx(Path source) throws IOException {
        try (InputStream input = java.nio.file.Files.newInputStream(source);
             XMLSlideShow slideshow = new XMLSlideShow(input)) {
            List<AiServerContract.Page> pages = new ArrayList<>();
            for (int index = 0; index < slideshow.getSlides().size(); index++) {
                addPage(pages, index + 1, slideshow.getSlides().get(index).getShapes().stream()
                        .filter(shape -> shape instanceof org.apache.poi.xslf.usermodel.XSLFTextShape)
                        .map(shape -> ((org.apache.poi.xslf.usermodel.XSLFTextShape) shape).getText())
                        .reduce("", (left, right) -> left + "\n" + right));
            }
            return requireText(pages);
        }
    }

    private List<AiServerContract.Page> extractPpt(Path source) throws IOException {
        try (InputStream input = java.nio.file.Files.newInputStream(source);
             HSLFSlideShow slideshow = new HSLFSlideShow(input)) {
            List<AiServerContract.Page> pages = new ArrayList<>();
            for (int index = 0; index < slideshow.getSlides().size(); index++) {
                addPage(pages, index + 1, slideshow.getSlides().get(index).getTextParagraphs().stream()
                        .flatMap(paragraphs -> paragraphs.stream())
                        .flatMap(paragraph -> paragraph.getTextRuns().stream())
                        .map(org.apache.poi.hslf.usermodel.HSLFTextRun::getRawText)
                        .reduce("", (left, right) -> left + "\n" + right));
            }
            return requireText(pages);
        }
    }

    private List<AiServerContract.Page> extractDocx(Path source) throws IOException {
        try (InputStream input = java.nio.file.Files.newInputStream(source);
             XWPFDocument document = new XWPFDocument(input)) {
            return requireText(List.of(new AiServerContract.Page(1, document.getParagraphs().stream()
                    .map(paragraph -> paragraph.getText()).reduce("", (left, right) -> left + "\n" + right))));
        }
    }

    private List<AiServerContract.Page> extractDoc(Path source) throws IOException {
        try (InputStream input = java.nio.file.Files.newInputStream(source);
             HWPFDocument document = new HWPFDocument(input)) {
            return requireText(List.of(new AiServerContract.Page(1, document.getRange().text())));
        }
    }

    private void addPage(List<AiServerContract.Page> pages, int pageNumber, String text) {
        if (text != null && !text.isBlank()) pages.add(new AiServerContract.Page(pageNumber, text.strip()));
    }

    private List<AiServerContract.Page> requireText(List<AiServerContract.Page> pages) {
        if (pages.isEmpty()) throw new IllegalArgumentException("파일에서 추출할 텍스트가 없습니다.");
        return pages;
    }

    private String extension(String originalName) {
        int dot = originalName == null ? -1 : originalName.lastIndexOf('.');
        return dot < 0 ? "" : originalName.substring(dot + 1).toLowerCase(Locale.ROOT);
    }
}
