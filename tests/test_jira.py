import os
import pytest
from spackle.jira import (
    JiraTicket, 
    JiraProject, 
    JiraComment,
    MarkdownFormatter,
    parse_jira_xml,
    format_ticket_markdown,
    parse_jira_to_markdown,
    preprocess_jira_xml,
    strip_html,
    convert_jira_browse_url_to_xml
)


class Paths:
    """Test paths helper similar to spackle.__init__.Paths"""
    def __init__(self):
        self.file = os.path.dirname(os.path.abspath(__file__))
        self.project = os.path.realpath(os.path.join(self.file, '..'))
        self.asset = os.path.join(self.project, 'asset')
        self.test = os.path.join(self.asset, 'test')


@pytest.fixture
def paths():
    return Paths()


@pytest.fixture
def sample_xml(paths):
    """Load the sanitized test XML file"""
    xml_path = os.path.join(paths.test, 'sample.xml')
    with open(xml_path, 'r', encoding='utf-8') as f:
        return f.read()


@pytest.fixture
def duplicate_rel_xml():
    """Create test XML with duplicate rel attributes"""
    return '''<rss version="0.92">
<channel>
<title>Jira</title>
<link>https://example.atlassian.net</link>
<description>Test file with duplicate rel attribute</description>
<item>
<title>[TEST-456] Test Issue with Duplicate Rel</title>
<link>https://example.atlassian.net/browse/TEST-456</link>
<key id="123456">TEST-456</key>
<summary>Test Issue with Duplicate Rel</summary>
<description>Test description</description>
<type>Bug</type>
<status>Open</status>
<priority>P2</priority>
<assignee accountid="user-001">Test User</assignee>
<reporter accountid="user-002">Another User</reporter>
<created>Mon, 19 May 2025 10:39:36 -0400</created>
<comments>
<comment id="11240113" author="user-003" created="Mon, 19 May 2025 10:39:36 -0400">
<p><a href="https://example.atlassian.net/secure/ViewProfile.jspa?accountId=user-004"
class="user-hover" rel="user-004"
data-account-id="user-004"
accountid="user-004" rel="noreferrer">Test User</a>
this is a test comment with duplicate rel attributes.</p>
</comment>
</comments>
</item>
</channel>
</rss>'''


class TestMarkdownFormatter:
    """Test the MarkdownFormatter class"""
    
    def test_formatter_initialization(self):
        formatter = MarkdownFormatter()
        assert formatter.lines == []
    
    def test_add_header(self):
        formatter = MarkdownFormatter()
        formatter.add_header("Test Header", 1)
        assert formatter.lines == ["# Test Header", ""]
        
        formatter.add_header("Sub Header", 2)
        assert formatter.lines == ["# Test Header", "", "## Sub Header", ""]
    
    def test_add_line(self):
        formatter = MarkdownFormatter()
        formatter.add_line("Test line")
        assert formatter.lines == ["Test line"]
    
    def test_add_line_break(self):
        formatter = MarkdownFormatter()
        formatter.add_line_break()
        assert formatter.lines == [""]
    
    def test_add_field_with_value(self):
        formatter = MarkdownFormatter()
        formatter.add_field("Status", "Open")
        assert formatter.lines == ["**Status:** Open"]
    
    def test_add_field_with_none_value(self):
        formatter = MarkdownFormatter()
        formatter.add_field("Status", None)
        assert formatter.lines == []
    
    def test_add_field_with_empty_value(self):
        formatter = MarkdownFormatter()
        formatter.add_field("Status", "")
        assert formatter.lines == []
    
    def test_add_list_with_items(self):
        formatter = MarkdownFormatter()
        formatter.add_list("Components", ["Core", "UI", "API"])
        assert formatter.lines == ["**Components:** Core, UI, API"]
    
    def test_add_list_with_empty_list(self):
        formatter = MarkdownFormatter()
        formatter.add_list("Components", [])
        assert formatter.lines == []
    
    def test_add_section_with_content(self):
        formatter = MarkdownFormatter()
        formatter.add_section("Description", "This is a test description")
        assert formatter.lines == ["## Description", "", "This is a test description", ""]
    
    def test_add_section_with_empty_content(self):
        formatter = MarkdownFormatter()
        formatter.add_section("Description", "")
        assert formatter.lines == []
    
    def test_add_bullet_list(self):
        formatter = MarkdownFormatter()
        items = [("Field1", "Value1"), ("Field2", ["Value2a", "Value2b"])]
        formatter.add_bullet_list(items)
        expected = ["- **Field1:** Value1", "- **Field2:** Value2a, Value2b"]
        assert formatter.lines == expected
    
    def test_get_markdown(self):
        formatter = MarkdownFormatter()
        formatter.add_header("Test", 1)
        formatter.add_line("Content")
        result = formatter.get_markdown()
        assert result == "# Test\n\nContent"


class TestPreprocessing:
    """Test XML preprocessing functions"""
    
    def test_strip_html_simple(self):
        html = "<p>Hello <b>world</b></p>"
        result = strip_html(html)
        assert result == "Hello world"
    
    def test_strip_html_with_br(self):
        html = "Line 1<br/>Line 2"
        result = strip_html(html)
        assert "Line 1\nLine 2" in result
    
    def test_strip_html_empty(self):
        result = strip_html("")
        assert result == ""
    
    def test_strip_html_none(self):
        result = strip_html(None)
        assert result == ""
    
    def test_preprocess_jira_xml_duplicate_rel(self, duplicate_rel_xml):
        """Test that duplicate rel attributes are fixed"""
        processed = preprocess_jira_xml(duplicate_rel_xml)
        # Should not have duplicate rel attributes
        assert 'rel="user-004"' not in processed or processed.count('rel="user-004"') == 1
        # Should have combined rel attribute
        assert 'rel="user-004 noreferrer"' in processed
    
    def test_preprocess_jira_xml_ampersand_replacement(self):
        xml = "<description>This & that</description>"
        result = preprocess_jira_xml(xml)
        assert "This that" in result  # & replaced with space


class TestJiraDataclasses:
    """Test the Jira dataclass structures"""
    
    def test_jira_project_creation(self):
        project = JiraProject(name="Test Project", id="123", key="TEST")
        assert project.name == "Test Project"
        assert project.id == "123" 
        assert project.key == "TEST"
    
    def test_jira_comment_creation(self):
        comment = JiraComment(
            author="john.doe", 
            created="2025-01-01", 
            text="Test comment"
        )
        assert comment.author == "john.doe"
        assert comment.created == "2025-01-01"
        assert comment.text == "Test comment"
    
    def test_jira_ticket_creation_minimal(self):
        ticket = JiraTicket(
            key="TEST-123",
            title="Test Issue",
            summary="Test Summary", 
            description="Test Description",
            link="https://example.com/TEST-123"
        )
        assert ticket.key == "TEST-123"
        assert ticket.title == "Test Issue"
        assert ticket.summary == "Test Summary"
        assert ticket.description == "Test Description"
        assert ticket.link == "https://example.com/TEST-123"
        # Test defaults
        assert ticket.project is None
        assert ticket.components == []
        assert ticket.labels == []
        assert ticket.comments == []
        assert ticket.custom_fields == {}


class TestJiraXmlParsing:
    """Test parsing of actual Jira XML"""
    
    def test_parse_jira_xml_success(self, sample_xml):
        """Test successful parsing of sample XML"""
        ticket = parse_jira_xml(sample_xml)
        
        assert ticket is not None
        assert isinstance(ticket, JiraTicket)
        assert ticket.key == "TEST-123"
        assert "Lorem Ipsum Software" in ticket.title
        assert ticket.link == "https://example.atlassian.net/browse/TEST-123"
        assert ticket.type == "Bug"
        assert ticket.status == "More Info"
        assert ticket.priority == "P3"
        assert ticket.assignee == "John Doe"
        assert ticket.reporter == "Jane Smith"
    
    def test_parse_jira_xml_project_info(self, sample_xml):
        """Test project information extraction"""
        ticket = parse_jira_xml(sample_xml)
        
        assert ticket.project is not None
        assert ticket.project.name == "Example Project Services"
        assert ticket.project.key == "TEST"
        assert ticket.project.id == "10119"
    
    def test_parse_jira_xml_components_and_labels(self, sample_xml):
        """Test components and labels extraction"""
        ticket = parse_jira_xml(sample_xml)
        
        assert "Core Component" in ticket.components
        assert "Example_Template" in ticket.labels
        assert "example_label" in ticket.labels
        assert "support_label" in ticket.labels
    
    def test_parse_jira_xml_comments(self, sample_xml):
        """Test comments extraction"""
        ticket = parse_jira_xml(sample_xml)
        
        assert len(ticket.comments) > 0
        first_comment = ticket.comments[0]
        assert isinstance(first_comment, JiraComment)
        assert first_comment.author == "user-id-003"
        assert "Lorem ipsum dolor" in first_comment.text
    
    def test_parse_jira_xml_custom_fields(self, sample_xml):
        """Test custom fields extraction"""
        ticket = parse_jira_xml(sample_xml)
        
        assert len(ticket.custom_fields) > 0
        assert "Actual Discovery Stage" in ticket.custom_fields
        assert ticket.custom_fields["Actual Discovery Stage"] == "SE12 Customer Lab"
        assert "Severity" in ticket.custom_fields
        assert ticket.custom_fields["Severity"] == "S3"
    
    def test_parse_jira_xml_invalid_xml(self):
        """Test parsing with invalid XML"""
        invalid_xml = "<invalid>unclosed tag"
        with pytest.raises(ValueError, match="Failed to parse XML"):
            parse_jira_xml(invalid_xml)
    
    def test_parse_jira_xml_no_item(self):
        """Test parsing XML with no item element"""
        xml_no_item = "<rss><channel><title>Test</title></channel></rss>"
        with pytest.raises(ValueError, match="No ticket found in XML"):
            parse_jira_xml(xml_no_item)
    
    def test_parse_jira_xml_with_duplicate_rel(self, duplicate_rel_xml):
        """Test parsing XML with duplicate rel attributes"""
        ticket = parse_jira_xml(duplicate_rel_xml)
        
        assert ticket is not None
        assert ticket.key == "TEST-456" 
        assert ticket.title == "[TEST-456] Test Issue with Duplicate Rel"
        assert len(ticket.comments) > 0


class TestMarkdownGeneration:
    """Test markdown generation from tickets"""
    
    def test_format_ticket_markdown_basic(self):
        """Test basic markdown formatting"""
        ticket = JiraTicket(
            key="TEST-123",
            title="[TEST-123] Test Issue",
            summary="Test Summary",
            description="Test description",
            link="https://example.com/TEST-123",
            type="Bug",
            status="Open",
            priority="High"
        )
        
        markdown = format_ticket_markdown(ticket)
        
        assert "# TEST-123: Test Summary" in markdown
        assert "**Link:** https://example.com/TEST-123" in markdown
        assert "**Type:** Bug" in markdown
        assert "**Status:** Open" in markdown
        assert "**Priority:** High" in markdown
        assert "## Description" in markdown
        assert "Test description" in markdown
    
    def test_format_ticket_markdown_with_project(self):
        """Test markdown formatting with project info"""
        project = JiraProject(name="Test Project", id="123", key="TEST")
        ticket = JiraTicket(
            key="TEST-123",
            title="Test Issue",
            summary="Test Summary",
            description="Test description", 
            link="https://example.com/TEST-123",
            project=project
        )
        
        markdown = format_ticket_markdown(ticket)
        
        assert "**Project:** Test Project (TEST, ID: 123)" in markdown
    
    def test_format_ticket_markdown_with_comments(self):
        """Test markdown formatting with comments"""
        comment = JiraComment(
            author="john.doe",
            created="2025-01-01",
            text="Test comment text"
        )
        ticket = JiraTicket(
            key="TEST-123",
            title="Test Issue", 
            summary="Test Summary",
            description="Test description",
            link="https://example.com/TEST-123",
            comments=[comment]
        )
        
        markdown = format_ticket_markdown(ticket)
        
        assert "## Comments" in markdown
        assert "### Comment 1" in markdown
        assert "**Author:** john.doe" in markdown
        assert "**Created:** 2025-01-01" in markdown
        assert "Test comment text" in markdown
    
    def test_format_ticket_markdown_with_custom_fields(self):
        """Test markdown formatting with custom fields"""
        ticket = JiraTicket(
            key="TEST-123",
            title="Test Issue",
            summary="Test Summary", 
            description="Test description",
            link="https://example.com/TEST-123",
            custom_fields={
                "Severity": "High",
                "Source": "Internal",
                "Multi Value Field": ["Value1", "Value2"]
            }
        )
        
        markdown = format_ticket_markdown(ticket)
        
        assert "## Custom Fields" in markdown
        assert "- **Severity:** High" in markdown
        assert "- **Source:** Internal" in markdown
        assert "- **Multi Value Field:** Value1, Value2" in markdown
    
    def test_parse_jira_to_markdown_success(self, sample_xml):
        """Test end-to-end parsing and markdown generation"""
        markdown = parse_jira_to_markdown(sample_xml)
        
        assert "# TEST-123:" in markdown
        assert "**Link:** https://example.atlassian.net/browse/TEST-123" in markdown
        assert "**Type:** Bug" in markdown
        assert "## Description" in markdown
        assert "## Comments" in markdown
        assert "## Custom Fields" in markdown
    
    def test_parse_jira_to_markdown_invalid_xml(self):
        """Test error handling in end-to-end function"""
        invalid_xml = "<invalid>unclosed"
        result = parse_jira_to_markdown(invalid_xml)
        
        assert result.startswith("Error:")
        assert "Failed to parse XML" in result
    
    def test_parse_jira_to_markdown_no_ticket(self):
        """Test error handling when no ticket found"""
        xml_no_ticket = "<rss><channel><title>Empty</title></channel></rss>"
        result = parse_jira_to_markdown(xml_no_ticket)
        
        assert result.startswith("Error:")
        assert "No ticket found in XML" in result


class TestIntegration:
    """Integration tests using real test files"""
    
    def test_full_workflow_with_test_file(self, sample_xml):
        """Test the complete workflow with the sanitized test file"""
        # Parse the XML
        ticket = parse_jira_xml(sample_xml)
        
        # Verify key data extracted correctly
        assert ticket.key == "TEST-123"
        assert ticket.type == "Bug"
        assert ticket.priority == "P3"
        assert len(ticket.comments) >= 4  # Should have multiple comments
        
        # Generate markdown
        markdown = format_ticket_markdown(ticket)
        
        # Verify markdown structure
        assert "# TEST-123:" in markdown
        assert "**Project:** Example Project Services" in markdown
        assert "**Components:** Core Component" in markdown
        assert "**Labels:** Example_Template, example_label, support_label" in markdown
        assert "## Description" in markdown
        assert "## Custom Fields" in markdown
        assert "## Comments" in markdown
        
        # Verify some specific content
        assert "Lorem ipsum" in markdown  # Should have lorem ipsum content
        assert "component-bundle-v1.234" in markdown  # Should have dummy versions
    
    def test_duplicate_rel_handling(self, duplicate_rel_xml):
        """Test that duplicate rel attributes are handled correctly"""
        # Should not raise an exception
        ticket = parse_jira_xml(duplicate_rel_xml)
        markdown = format_ticket_markdown(ticket)
        
        assert ticket.key == "TEST-456"
        assert "Test Issue with Duplicate Rel" in markdown
        
        # Should have successfully parsed the comment with duplicate rel
        assert len(ticket.comments) > 0
        comment_text = ticket.comments[0].text
        assert "test comment" in comment_text.lower()


class TestURLConversion:
    """Test URL conversion functions"""
    
    def test_convert_jira_browse_url_to_xml_basic(self):
        """Test basic browse URL to XML conversion"""
        browse_url = "https://example.atlassian.net/browse/SLG-999"
        expected = "https://example.atlassian.net/si/jira.issueviews:issue-xml/SLG-999/SLG-999.xml"
        result = convert_jira_browse_url_to_xml(browse_url)
        assert result == expected
    
    def test_convert_jira_browse_url_to_xml_with_subdomain(self):
        """Test browse URL conversion with complex domain"""
        browse_url = "https://ncrvoyix-saas.atlassian.net/browse/EFS-8517"
        expected = "https://ncrvoyix-saas.atlassian.net/si/jira.issueviews:issue-xml/EFS-8517/EFS-8517.xml"
        result = convert_jira_browse_url_to_xml(browse_url)
        assert result == expected
    
    def test_convert_jira_browse_url_to_xml_complex_ticket_key(self):
        """Test with complex ticket key"""
        browse_url = "https://example.atlassian.net/browse/PROJECT-12345"
        expected = "https://example.atlassian.net/si/jira.issueviews:issue-xml/PROJECT-12345/PROJECT-12345.xml"
        result = convert_jira_browse_url_to_xml(browse_url)
        assert result == expected
    
    def test_convert_jira_browse_url_to_xml_non_browse_url(self):
        """Test that non-browse URLs are returned unchanged"""
        xml_url = "https://example.atlassian.net/si/jira.issueviews:issue-xml/SLG-999/SLG-999.xml"
        result = convert_jira_browse_url_to_xml(xml_url)
        assert result == xml_url
    
    def test_convert_jira_browse_url_to_xml_malformed_browse_url(self):
        """Test with malformed browse URL"""
        malformed_url = "https://example.atlassian.net/browse/"
        result = convert_jira_browse_url_to_xml(malformed_url)
        assert result == malformed_url  # Should return original if can't parse
    


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])