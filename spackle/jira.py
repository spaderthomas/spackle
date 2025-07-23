import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from lxml import etree
from lxml.html import fromstring, tostring
import requests


@dataclass
class JiraProject:
  name: str
  id: str
  key: str


@dataclass
class JiraComment:
  author: str
  created: str
  text: str


@dataclass
class JiraTicket:
  # Core fields
  key: str
  title: str
  summary: str
  description: str
  link: str

  # Project info
  project: Optional[JiraProject] = None

  # Standard fields
  type: Optional[str] = None
  status: Optional[str] = None
  priority: Optional[str] = None
  resolution: Optional[str] = None
  assignee: Optional[str] = None
  reporter: Optional[str] = None

  # Dates
  created: Optional[str] = None
  updated: Optional[str] = None
  resolved: Optional[str] = None

  # Other fields
  environment: Optional[str] = None
  timespent: Optional[str] = None
  votes: Optional[str] = None
  watches: Optional[str] = None

  # Collections
  components: List[str] = field(default_factory=list)
  labels: List[str] = field(default_factory=list)
  comments: List[JiraComment] = field(default_factory=list)
  custom_fields: Dict[str, Any] = field(default_factory=dict)


class MarkdownFormatter:
  def __init__(self):
    self.lines: List[str] = []

  def add_header(self, text: str, level: int = 1) -> None:
    self.lines.append(f'{"#" * level} {text}')
    self.lines.append('')

  def add_line(self, text: str) -> None:
    self.lines.append(text)

  def add_line_break(self) -> None:
    self.lines.append('')

  def add_field(self, label: str, value: Optional[str]) -> None:
    if value:
      self.lines.append(f'**{label}:** {value}')

  def add_list(self, label: str, items: List[str]) -> None:
    if items:
      self.lines.append(f'**{label}:** {", ".join(items)}')

  def add_section(self, title: str, content: str, level: int = 2) -> None:
    if content:
      self.add_header(title, level)
      self.lines.append(content)
      self.lines.append('')

  def add_bullet_list(self, items: List[tuple[str, Any]]) -> None:
    for key, value in items:
      if isinstance(value, list):
        value = ', '.join(str(v) for v in value)
      self.lines.append(f'- **{key}:** {value}')

  def get_markdown(self) -> str:
    result = []
    for i, line in enumerate(self.lines):
      result.append(line)
      # Add double newline after non-empty lines that aren't followed by empty lines
      if (
        line
        and i < len(self.lines) - 1
        and self.lines[i + 1]
        and not line.startswith('- ')
        and not self.lines[i + 1].startswith('- ')
      ):
        result.append('')
    return '\n'.join(result)


def strip_html(html_text: str) -> str:
  if not html_text:
    return ''

  try:
    # Parse HTML
    doc = fromstring(html_text)

    # Convert br and p tags to newlines
    for br in doc.xpath('//br'):
      br.tail = '\n' + (br.tail or '')

    for p in doc.xpath('//p'):
      p.text = '\n' + (p.text or '')
      p.tail = '\n' + (p.tail or '')

    # Get text content
    text = doc.text_content()

    # Clean up excessive whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)

    return text.strip()
  except Exception:
    # Fallback to simple regex if lxml fails
    text = re.sub(r'<br\s*/?>', '\n', html_text)
    text = re.sub(r'</p>', '\n\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()


def preprocess_jira_xml(xml_content: str) -> str:
  # Strip everything before the first '<'
  first_bracket = xml_content.find('<')
  if first_bracket > 0:
    xml_content = xml_content[first_bracket:]

  # Replace unescaped ampersands in text (not URL params or entities)
  xml_content = xml_content.replace(' & ', ' ')

  # Fix duplicate rel attributes in anchor tags
  # Pattern: rel="value1" ... rel="value2" -> rel="value1 value2"
  import re

  pattern = r'(<a[^>]*?)rel="([^"]+)"([^>]*?)rel="([^"]+)"'
  xml_content = re.sub(pattern, r'\1rel="\2 \4"\3', xml_content)

  return xml_content


def get_text(parent, tag: str) -> Optional[str]:
  elem = parent.find(tag)
  return elem.text if elem is not None and elem.text else None


def extract_all_text(element) -> str:
  if element is None:
    return ''

  texts = []

  # Get direct text content
  if element.text:
    texts.append(element.text.strip())

  # Recursively get text from all children
  for child in element:
    # Handle different HTML elements for proper markdown formatting
    if child.tag.lower() in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
      # Paragraph-like elements get double newlines
      child_text = extract_all_text(child)
      if child_text:
        texts.append('\n' + child_text + '\n')
    elif child.tag.lower() in ['li']:
      # List items get bullet points - handle br tags within li as newlines
      child_text = extract_all_text(child)
      if child_text:
        # Split on newlines and make each a separate list item
        lines = [line.strip() for line in child_text.split('\n') if line.strip()]
        for line in lines:
          texts.append('\n- ' + line)
    elif child.tag.lower() in ['ul', 'ol']:
      # Lists - just process children
      child_text = extract_all_text(child)
      if child_text:
        texts.append(child_text)
    elif child.tag.lower() in ['br']:
      # Line breaks
      texts.append('\n')
    else:
      # Other elements just get their text
      child_text = extract_all_text(child)
      if child_text:
        texts.append(child_text)

    # Get tail text (text after closing tag)
    if child.tail and child.tail.strip():
      texts.append(child.tail.strip())

  # Join and clean up excessive whitespace
  result = ''.join(texts)
  # Replace multiple newlines with double newlines for proper paragraph spacing
  result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
  # Fix double dashes at start of lines to be proper list items
  result = re.sub(r'\n--([^\-])', r'\n- \1', result)
  result = re.sub(r'^--([^\-])', r'- \1', result)
  return result.strip()


def parse_jira_xml(xml_content: str) -> Optional[JiraTicket]:
  try:
    # Preprocess the XML to fix Jira's invalid XML
    xml_content = preprocess_jira_xml(xml_content)

    root = etree.fromstring(xml_content.encode('utf-8'))
  except Exception as e:
    raise ValueError(f'Failed to parse XML: {str(e)}')

  # Find the first item (ticket)
  item = root.find('.//item')
  if item is None:
    raise ValueError('No ticket found in XML')

  # Extract basic fields
  title = get_text(item, 'title') or ''
  link = get_text(item, 'link') or ''

  # Extract ticket key from title (e.g., [EFS-9211])
  key = ''
  title_match = re.match(r'\[([A-Z]+-\d+)\]', title)
  if title_match:
    key = title_match.group(1)

  # Extract project info
  project = None
  project_elem = item.find('project')
  if project_elem is not None:
    project = JiraProject(
      name=project_elem.text or '',
      id=project_elem.get('id', ''),
      key=project_elem.get('key', ''),
    )

  # Extract and clean description
  description = ''
  description_elem = item.find('description')
  if description_elem is not None:
    description = extract_all_text(description_elem)

  # Create ticket object
  ticket = JiraTicket(
    key=key,
    title=title,
    summary=get_text(item, 'summary') or '',
    description=description,
    link=link,
    project=project,
    type=get_text(item, 'type'),
    status=get_text(item, 'status'),
    priority=get_text(item, 'priority'),
    resolution=get_text(item, 'resolution'),
    assignee=get_text(item, 'assignee'),
    reporter=get_text(item, 'reporter'),
    created=get_text(item, 'created'),
    updated=get_text(item, 'updated'),
    resolved=get_text(item, 'resolved'),
    environment=get_text(item, 'environment'),
    timespent=get_text(item, 'timespent'),
    votes=get_text(item, 'votes'),
    watches=get_text(item, 'watches'),
  )

  # Extract components
  components = item.findall('component')
  if components:
    ticket.components = [comp.text for comp in components if comp.text]

  # Extract labels
  labels = item.findall('labels/label')
  if labels:
    ticket.labels = [label.text for label in labels if label.text]

  # Extract custom fields
  customfields_elem = item.find('customfields')
  if customfields_elem is not None:
    for field in customfields_elem.findall('customfield'):
      field_id = field.get('id', '')
      field_key = field.get('key', '')
      field_name_elem = field.find('customfieldname')
      field_name = field_name_elem.text if field_name_elem is not None else field_id

      # Extract field values
      values_elem = field.find('customfieldvalues')
      if values_elem is not None:
        values = []
        for value_elem in values_elem.findall('customfieldvalue'):
          if value_elem.text:
            values.append(strip_html(value_elem.text))

        if values:
          ticket.custom_fields[field_name] = values if len(values) > 1 else values[0]

  # Extract comments
  comments = item.findall('.//comment')
  if comments:
    for comment in comments:
      comment_text = extract_all_text(comment) if comment is not None else ''
      comment_obj = JiraComment(
        author=comment.get('author', ''),
        created=comment.get('created', ''),
        text=comment_text,
      )
      ticket.comments.append(comment_obj)

  return ticket


def format_ticket_markdown(ticket: JiraTicket) -> str:
  formatter = MarkdownFormatter()

  # Title
  if ticket.key:
    display_title = (
      ticket.summary
      if ticket.summary
      else ticket.title.replace(f'[{ticket.key}]', '').strip()
    )
    formatter.add_header(f'{ticket.key}: {display_title}')
  else:
    formatter.add_header(ticket.summary if ticket.summary else ticket.title)

  # Link
  formatter.add_field('Link', ticket.link)
  if ticket.link:
    formatter.add_line_break()

  # Project info
  if ticket.project:
    formatter.add_line(
      f'**Project:** {ticket.project.name} ({ticket.project.key}, ID: {ticket.project.id})'
    )
    formatter.add_line_break()

  # Basic fields
  basic_fields = [
    ('Type', ticket.type),
    ('Status', ticket.status),
    ('Priority', ticket.priority),
    ('Resolution', ticket.resolution),
    ('Assignee', ticket.assignee),
    ('Reporter', ticket.reporter),
    ('Created', ticket.created),
    ('Updated', ticket.updated),
    ('Resolved', ticket.resolved),
    ('Environment', ticket.environment),
    ('Time Spent', ticket.timespent),
    ('Votes', ticket.votes),
    ('Watches', ticket.watches),
  ]

  # Add non-empty fields
  fields_added = False
  for label, value in basic_fields:
    if value:
      formatter.add_field(label, value)
      fields_added = True

  if fields_added:
    formatter.add_line_break()

  # Components and labels
  formatter.add_list('Components', ticket.components)
  if ticket.components:
    formatter.add_line_break()

  formatter.add_list('Labels', ticket.labels)
  if ticket.labels:
    formatter.add_line_break()

  # Description
  formatter.add_section('Description', ticket.description)

  # Custom fields
  if ticket.custom_fields:
    formatter.add_header('Custom Fields', 2)
    formatter.add_bullet_list(list(ticket.custom_fields.items()))
    formatter.add_line_break()

  # Comments
  if ticket.comments:
    formatter.add_header('Comments', 2)
    for i, comment in enumerate(ticket.comments, 1):
      formatter.add_header(f'Comment {i}', 3)
      formatter.add_field('Author', comment.author)
      formatter.add_field('Created', comment.created)
      formatter.add_line_break()
      formatter.add_line(comment.text)
      formatter.add_line_break()

  return formatter.get_markdown()


def convert_jira_browse_url_to_xml(browse_url: str) -> str:
  parsed_url = urllib.parse.urlparse(browse_url)

  if '/browse/' in parsed_url.path:
    path_parts = parsed_url.path.split('/browse/')
    if len(path_parts) == 2:
      ticket_key = path_parts[1].strip()
      # Only convert if we have a valid ticket key
      if ticket_key:
        xml_path = f'/si/jira.issueviews:issue-xml/{ticket_key}/{ticket_key}.xml'
        return urllib.parse.urlunparse(
          (parsed_url.scheme, parsed_url.netloc, xml_path, '', '', '')
        )

  return browse_url


def fetch_jira_xml_from_url(url: str, timeout: int = 10) -> str:
  jira_fields = [
    'key',
    'summary',
    'description',
    'comments',
    'customfield',
    'project',
    'type',
    'priority',
    'status',
    'resolution',
    'assignee',
    'reporter',
    'created',
    'updated',
    'resolved',
    'component',
    'labels',
    'environment',
    'timespent',
    'votes',
    'watches',
  ]

  # Convert browse URLs to XML format
  url = convert_jira_browse_url_to_xml(url)

  parsed_url = urllib.parse.urlparse(url)
  query_params = urllib.parse.parse_qs(parsed_url.query)

  for field in jira_fields:
    if 'field' not in query_params:
      query_params['field'] = []
    query_params['field'].append(field)

  new_query = urllib.parse.urlencode(query_params, doseq=True)
  xml_url = urllib.parse.urlunparse(
    (
      parsed_url.scheme,
      parsed_url.netloc,
      parsed_url.path,
      parsed_url.params,
      new_query,
      parsed_url.fragment,
    )
  )

  response = requests.get(xml_url, timeout=timeout)
  response.raise_for_status()
  return response.text


def parse_jira_to_markdown(xml_content: str) -> str:
  try:
    ticket = parse_jira_xml(xml_content)
    return format_ticket_markdown(ticket)
  except ValueError as e:
    return f'Error: {str(e)}'
  except Exception as e:
    return f'Unexpected error: {str(e)}'
